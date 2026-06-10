# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス
import plotly.graph_objects as go  # グラフを描くためのライブラリ
import json     # JSONデータを扱うためのライブラリ
import base64   # 画像をテキストデータに変換するためのライブラリ
import re       # ドメイン名の整形（英数字以外の除去）に使用
import requests # RDAP（ドメイン登録情報の公開API）への問い合わせに使用

# =====================================================================
# ページ設定とデザイン（CSS）
# =====================================================================
st.set_page_config(page_title="Namers AI", page_icon="🪶", layout="centered")

st.markdown("""
<style>
    button[data-baseweb="tab"] p { font-size: 0.95rem; }
    button[data-baseweb="tab"][aria-selected="true"] p { font-weight: 700; }
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    [data-testid="stCode"] { margin-bottom: 0.3rem; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 設定値（上限・シークレット）
# =====================================================================
# 【改善5】1セッションあたりのAPI実行回数の上限（コスト保護）
# ※session_stateベースなのでページ再読み込みでリセットされる「簡易的な」保護です。
#   厳密に守るにはサーバー側のデータベース等での記録が必要です。
USAGE_LIMITS = {"gen": 10, "eval": 5, "tm": 5, "dom": 15}
USAGE_LABELS = {"gen": "名前生成", "eval": "詳細診断", "tm": "商標チェック", "dom": "ドメイン確認"}

# 【改善4】アクセスコードをソースコードから分離
# Streamlit Cloudの「Settings → Secrets」に PREMIUM_CODE = "新しいコード" を設定してください。
# 下のフォールバック値はローカル開発用です。公開リポジトリに置く場合は削除を推奨します。
try:
    SECRET_CODE = st.secrets["PREMIUM_CODE"]
except Exception:
    SECRET_CODE = "copenhagen"  # ←ローカル開発用フォールバック（要変更・要削除）

# 評価の判断軸の選択肢【改善2】
BASE_AXES = ["響き", "字形", "独創", "可読", "願い"]
EXTRA_AXES = ["国際性", "呼びやすさ", "記憶しやすさ", "古風さ", "先進性", "親しみやすさ", "力強さ"]

# =====================================================================
# セッション状態の初期化
# =====================================================================
if 'generated_names' not in st.session_state:
    st.session_state.generated_names = []   # 生成履歴（CSV保存用）
if 'last_results' not in st.session_state:
    st.session_state.last_results = None    # 直近の生成結果
if 'last_axes' not in st.session_state:
    st.session_state.last_axes = BASE_AXES  # 直近の生成で使った判断軸
if 'last_conditions' not in st.session_state:
    st.session_state.last_conditions = None # 直近の生成条件（派生生成に使用）
if 'favorites' not in st.session_state:
    st.session_state.favorites = []         # お気に入りリスト
if 'usage' not in st.session_state:
    st.session_state.usage = {k: 0 for k in USAGE_LIMITS}  # API実行回数カウンタ
if 'derive_base' not in st.session_state:
    st.session_state.derive_base = None     # 「近い案をもっと」の基点となる名前

# =====================================================================
# 共通関数
# =====================================================================
def check_limit(kind):
    """【改善5】実行回数の上限チェック。超過していたらFalseを返しエラー表示。"""
    if st.session_state.usage[kind] >= USAGE_LIMITS[kind]:
        st.error(
            f"このセッションでの「{USAGE_LABELS[kind]}」の上限（{USAGE_LIMITS[kind]}回）に達しました。"
            "APIコスト管理のため制限を設けています。時間をおいてご利用ください。"
        )
        return False
    return True

def count_usage(kind):
    st.session_state.usage[kind] += 1

def remaining(kind):
    return USAGE_LIMITS[kind] - st.session_state.usage[kind]

@st.cache_data(show_spinner=False, ttl=3600)
def cached_completion(model, prompt):
    """【改善6】同一のモデル・プロンプトの結果を1時間キャッシュし、API呼び出しを節約する。
    （画像つきリクエストはキャッシュ対象外として別経路で処理）"""
    _client = OpenAI()
    response = _client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

@st.cache_data(show_spinner=False, ttl=600)
def check_domain_rdap(domain):
    """【改善1】RDAP（ドメイン登録情報の公開プロトコル）でドメインの登録有無を確認する。
    返り値: "registered"（登録済み） / "available"（おそらく未登録） / "unknown"（判定不能）"""
    try:
        r = requests.get(f"https://rdap.org/domain/{domain}", timeout=8, allow_redirects=True)
        if r.status_code == 200:
            return "registered"
        elif r.status_code == 404:
            return "available"
        else:
            return "unknown"
    except Exception:
        return "unknown"

def sanitize_domain_base(text):
    """ドメインに使える文字（英小文字・数字・ハイフン）だけを残す"""
    text = text.lower().strip()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^a-z0-9\-]", "", text)
    return text.strip("-")

def build_radar(axes, axis_scores, name, color='#00CC96'):
    """レーダーチャートを作る共通関数"""
    values = [axis_scores.get(a, 50) for a in axes]
    values += [values[0]]
    cats = list(axes) + [axes[0]]
    return go.Scatterpolar(r=values, theta=cats, fill='toself', name=name, line_color=color)

# --- タブ間連携用のコールバック関数 ---
def add_favorite(name, yomi, reason, score, axis_scores, axes):
    """お気に入りに追加（重複は無視）。比較ビュー用に軸ごとのスコアも保存する。"""
    if not any(f["名前"] == name for f in st.session_state.favorites):
        st.session_state.favorites.append({
            "名前": name, "読み": yomi, "総合点": score, "理由": reason,
            "軸スコア": axis_scores, "判断軸": list(axes),
            "追加日時": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

def send_to_trademark(name, yomi):
    st.session_state["tm_name_input"] = name
    st.session_state["tm_yomi_input"] = yomi
    st.toast(f"「{name}」を商標チェックタブにセットしました。タブを切り替えてください。", icon="🔍")

def send_to_eval(name, yomi):
    st.session_state["eval_name"] = name
    st.session_state["eval_yomi"] = yomi
    st.toast(f"「{name}」を詳細診断タブにセットしました。タブを切り替えてください。", icon="💎")

def request_derive(name, yomi):
    """【改善7】「この名前に近い案をもっと」のリクエストを記録（次の再実行で処理）"""
    st.session_state.derive_base = {"name": name, "yomi": yomi}

# タイトル
st.title("Namers AI　～AI名付け支援ツール～")
st.caption("名前の生成からプロ視点の診断、商標・ドメインの事前チェックまでを1つのアプリで。")

# OpenAIのクライアントを初期化
client = OpenAI()

# =====================================================================
# タブの作成
# =====================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "💡 名前を生成",
    "💎 詳細診断 (プレミアム)",
    "🔍 商標・ドメイン",
    "⭐ お気に入り・履歴"
])

# --------------------------------------------------
# 【タブ1】名前生成機能
# --------------------------------------------------
with tab1:
    with st.expander("👇 入力条件を開く（ここをタップ）", expanded=True):
        st.markdown("### 📋 名付けの条件")
        target_type = st.radio("名付けする対象", ["人間", "ペット", "キャラクター"], horizontal=True)

        col1, col2 = st.columns(2)
        with col1:
            surname = st.text_input("苗字（省略可）", placeholder="例：佐藤")
        with col2:
            gender = st.selectbox("性別", ["指定なし", "男", "女"])

        col3, col4 = st.columns(2)
        with col3:
            use_kanji = st.text_input("使いたい漢字（省略可）", placeholder="例：翔、愛")
        with col4:
            avoid_kanji = st.text_input("避けたい漢字(省略可）", placeholder="例：悪、死")

        st.markdown("##### 💡 どんな名前にしたい？（カテゴリから選択）")

        tag_categories = {
            "基本のイメージ": ["明るい", "元気", "優しい", "クール", "知的", "上品", "美しい", "かっこいい", "可愛い"],
            "自然・季節": ["春", "夏", "秋", "冬", "海・水", "空・宇宙", "太陽", "月・星", "花・植物", "宝石"],
            "時代・雰囲気": ["古風", "モダン", "和風", "洋風", "レトロ", "未来風", "神秘的"],
            "個性・色": ["国際的", "ユニーク", "中性的", "赤", "青", "黄", "白", "黒", "茶", "紫", "緑", "橙", "灰", "桃"],
            "音・響き": ["2文字", "3文字", "呼びやすい", "和風の響き", "洋風の響き"],
            "キャラ・物語": ["勇者", "悪役", "魔法使い", "騎士", "姫・貴族", "最強", "儚い", "狂気", "ゴシック"]
        }

        selected_tags = []
        for category_name, tags_list in tag_categories.items():
            with st.expander(f"🔽 {category_name}", expanded=False):
                selections = st.pills(
                    f"{category_name}を選択", tags_list, selection_mode="multi",
                    key=f"tag_{category_name}", label_visibility="collapsed"
                )
                if selections:
                    selected_tags.extend(selections)

        if selected_tags:
            st.caption(f"選択中: {', '.join(selected_tags)}")

        tags = selected_tags
        wish = st.text_area("その他の願い・詳細（任意）", placeholder="例：春生まれなので、温かいイメージを入れたい")

    # 【改善2・8】生成設定：判断軸のカスタマイズ・生成数・モデル切替
    with st.expander("⚙️ 生成設定（判断軸・生成数・モデル）", expanded=False):
        st.markdown("##### 📐 あなたの判断軸を選ぶ")
        st.caption("AIが点数をつける「ものさし」を自分で決められます。あなたが重視する軸で候補を見比べてください。")
        selected_axes = st.multiselect(
            "評価の判断軸（3〜6個）", BASE_AXES + EXTRA_AXES,
            default=BASE_AXES, max_selections=6
        )
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            num_names = st.selectbox("生成する候補の数", [3, 5], index=0)
        with col_g2:
            model_label = st.selectbox("使用するAIモデル", ["標準（速い・低コスト）", "高精度（じっくり考える）"])
        gen_model = "gpt-4o-mini" if model_label.startswith("標準") else "gpt-4o"

    uploaded_file = st.file_uploader("📸 写真やイラストからイメージする（任意）", type=['png', 'jpg', 'jpeg'])
    submit_btn = st.button("✨ AIに名前を考えてもらう", use_container_width=True, type="primary")
    st.caption(f"残り生成回数：{remaining('gen')} 回（このセッション中）")

    # --- スコアのJSON仕様を判断軸から動的に組み立てる ---
    def build_scores_spec(axes):
        axes_json = ", ".join([f'"{a}": 0〜100' for a in axes])
        return axes_json

    def run_generation(prompt, image_data_url, model):
        """生成APIを呼び、結果をsession_stateへ保存する共通処理"""
        if image_data_url:
            # 画像つきはキャッシュ対象外（画像データはキャッシュキーにできないため）
            messages = [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}}]}]
            response = client.chat.completions.create(
                model=model, messages=messages, response_format={"type": "json_object"})
            raw = response.choices[0].message.content
        else:
            raw = cached_completion(model, prompt)  # 【改善6】同一条件はキャッシュから返す
        return json.loads(raw)

    if submit_btn:
        if not wish and not uploaded_file and not selected_tags:
            st.warning("「雰囲気タグ」を選ぶか、「願い」の入力、または「画像」のアップロードをしてください！")
        elif len(selected_axes) < 3:
            st.warning("生成設定で判断軸を3つ以上選んでください。")
        elif check_limit("gen"):
            image_data_url = None
            if uploaded_file:
                encoded_image = base64.b64encode(uploaded_file.read()).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{encoded_image}"
                st.info("📸 画像のイメージも考慮して名前を考えます！")

            surname_instruction = f"苗字は「{surname}」です。" if surname else "苗字はありません。"

            prompt = f"""
            あなたはプロの命名アドバイザーです。
            以下の条件に基づいて、最適な名前を{num_names}つ提案してください。

            【入力情報】
            ・苗字：{surname_instruction}
            ・対象：{target_type}
            ・性別：{gender}
            ・使いたい漢字：{use_kanji}
            ・避けたい漢字：{avoid_kanji}
            【重要：イメージ・雰囲気】
            ・選択された雰囲気タグ：{", ".join(tags) if tags else "指定なし"}
            ・具体的な願い：{wish}
            ※「雰囲気タグ」と「具体的な願い」の両方を考慮して、イメージに合う名前を考案してください。
            ※画像が提供されている場合は、その視覚的イメージも反映してください。

【最重要：名前の言語・文字種のルール】
以下の優先順位（1が最強）で名前の雰囲気と文字種を決定してください。

1. **「洋風」「洋風の響き」タグ、または「外国風」の指定がある場合（最優先）：**
   ・苗字の有無に関わらず、**西洋的な響きを持つ名前**（例：アリス、レオ、エマ、アーサーなど）を提案してください。
   ・表記は**「カタカナ」を基本**としますが、ユーザーが「使いたい漢字」を指定している場合のみ「当て字」を使ってください。

2. 特定の国籍指定（「中国風」「韓国風」など）がある場合：
   ・その文化圏に合った名前と表記（中国・韓国なら漢字、その他はカタカナ）で提案してください。

3. 上記の指定がない場合（デフォルト）：
   ・苗字が「漢字」または「苗字なし」の場合：**日本人の名前（漢字・ひらがな）**を提案。
   ・苗字が「カタカナ」の場合：カタカナの名前を提案。
   ・対象が「ファンタジー」「キャラクター」の場合：世界観に合わせて自由選択。

            【重要：評価システム】
            ユーザーが選んだ以下の判断軸（各100点満点）と、「総合得点（100点満点）」を厳密に採点してください。
            判断軸：{", ".join(selected_axes)}
            ※「総合得点」は名前としての全体のバランス・完成度を加味してください。全体的に厳しめに採点してください。

            【出力形式（JSON）】
            必ず以下のJSONフォーマットのみを出力してください。
            {{
                "names": [
                    {{
                        "name": "名前の表記",
                        "yomi": "読み仮名",
                        "scores": {{
                            "total": 0〜100,
                            "axes": {{ {build_scores_spec(selected_axes)} }}
                        }},
                        "reason": "名前の語源・本来の意味を明記し、願いをどう叶えるか解説してください。"
                    }}
                ]
            }}
            """

            with st.spinner("💎 分析中..."):
                try:
                    result_json = run_generation(prompt, image_data_url, gen_model)
                    count_usage("gen")

                    st.session_state.last_results = result_json["names"]
                    st.session_state.last_axes = list(selected_axes)
                    # 【改善7】派生生成のために条件一式を保存
                    st.session_state.last_conditions = {
                        "target_type": target_type, "surname": surname, "gender": gender,
                        "use_kanji": use_kanji, "avoid_kanji": avoid_kanji,
                        "tags": list(tags), "wish": wish, "axes": list(selected_axes),
                        "model": gen_model
                    }

                    for item in result_json["names"]:
                        st.session_state.generated_names.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "対象": target_type,
                            "名前": f"{item['name']} ({item['yomi']})",
                            "総合点": item["scores"].get("total", 80),
                            "理由": item["reason"]
                        })

                    st.success("生成が完了しました！")

                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
                    st.session_state.last_results = None

    # --- 【改善7】「この名前に近い案をもっと」の処理 ---
    if st.session_state.derive_base and st.session_state.last_conditions:
        base = st.session_state.derive_base
        cond = st.session_state.last_conditions
        st.session_state.derive_base = None  # 二重実行を防ぐため先にクリア

        if check_limit("gen"):
            derive_prompt = f"""
            あなたはプロの命名アドバイザーです。
            ユーザーは「{base['name']}（{base['yomi']}）」という名前を気に入りました。
            この名前の方向性（響きの系統・雰囲気・文字種）に近い別の名前を3つ提案してください。
            ※「{base['name']}」そのものや、1文字だけ変えた安易な変形は避け、同じ方向性の新しい案を出すこと。

            【元の条件】
            ・対象：{cond['target_type']} ・苗字：{cond['surname'] or "なし"} ・性別：{cond['gender']}
            ・使いたい漢字：{cond['use_kanji']} ・避けたい漢字：{cond['avoid_kanji']}
            ・雰囲気タグ：{", ".join(cond['tags']) if cond['tags'] else "指定なし"}
            ・願い：{cond['wish']}

            【評価システム】
            判断軸（各100点満点）：{", ".join(cond['axes'])} と「総合得点」を厳しめに採点してください。

            【出力形式（JSON）】
            必ず以下のJSONフォーマットのみを出力してください。
            {{
                "names": [
                    {{
                        "name": "名前の表記",
                        "yomi": "読み仮名",
                        "scores": {{
                            "total": 0〜100,
                            "axes": {{ {build_scores_spec(cond['axes'])} }}
                        }},
                        "reason": "名前の語源・本来の意味と、元の名前とどう方向性が近いかを解説してください。"
                    }}
                ]
            }}
            """
            with st.spinner(f"🌱 「{base['name']}」に近い案を考え中..."):
                try:
                    raw = cached_completion(cond["model"], derive_prompt)
                    result_json = json.loads(raw)
                    count_usage("gen")

                    st.session_state.last_results = result_json["names"]
                    st.session_state.last_axes = list(cond["axes"])
                    for item in result_json["names"]:
                        st.session_state.generated_names.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "対象": cond["target_type"],
                            "名前": f"{item['name']} ({item['yomi']})",
                            "総合点": item["scores"].get("total", 80),
                            "理由": item["reason"]
                        })
                    st.success(f"「{base['name']}」に近い新しい案です！")
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

    # --- 生成結果の表示（セッションから描画するので操作後も消えない） ---
    if st.session_state.last_results:
        st.markdown("#### 🪶 提案された名前")
        axes_used = st.session_state.last_axes
        for i, item in enumerate(st.session_state.last_results):
            name, yomi, reason, scores = item["name"], item["yomi"], item["reason"], item["scores"]
            s_total = scores.get("total", 80)
            axis_scores = scores.get("axes", {})

            fig = go.Figure(data=[build_radar(axes_used, axis_scores, name)])
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False,
                              height=250, margin=dict(t=20, b=20, l=30, r=30))

            with st.container(border=True):
                col_text, col_graph = st.columns([1.2, 1])
                with col_text:
                    st.metric(label="🏅 総合評価", value=f"{s_total}点")
                    st.caption("名前（コピーできます👇）")
                    st.code(f"{name} ({yomi})", language=None)
                    st.write(f"**理由:** {reason}")
                with col_graph:
                    st.plotly_chart(fig, use_container_width=True, key=f"radar_{i}")

                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    st.button("⭐ 保存", key=f"fav_{i}", use_container_width=True,
                              on_click=add_favorite, args=(name, yomi, reason, s_total, axis_scores, axes_used))
                with b2:
                    st.button("🌱 近い案", key=f"dv_{i}", use_container_width=True,
                              on_click=request_derive, args=(name, yomi),
                              help="この名前の方向性に近い別の案を3つ生成します")
                with b3:
                    st.button("🔍 商標", key=f"tm_{i}", use_container_width=True,
                              on_click=send_to_trademark, args=(name, yomi))
                with b4:
                    st.button("💎 診断", key=f"ev_{i}", use_container_width=True,
                              on_click=send_to_eval, args=(name, yomi))

# --------------------------------------------------
# 【タブ2】プレミアム評価レポート（noteパスワード式）
# --------------------------------------------------
with tab2:
    st.markdown("### 💎 プレミアム詳細診断レポート")
    st.write("候補の名前を多角的に分析し、客観的なリスクや印象を評価するプロフェッショナル専用モードです。")

    note_url = "https://note.com/namersai/n/nd1fda095acbc?sub_rt=share_pb"

    with st.container(border=True):
        st.markdown("🔒 **この機能を利用するにはアクセスコードが必要です。（現在は無料公開中！）**")
        col_input, col_link = st.columns([2, 1])
        with col_input:
            user_password = st.text_input("アクセスコードを入力", type="password", placeholder="例：namers2026")
        with col_link:
            st.write(""); st.write("")
            st.link_button("コードを取得(noteへ)", note_url, use_container_width=True)

    if user_password == SECRET_CODE:
        st.success("✅ 認証成功！プレミアム機能が解放されました。")

        st.markdown("#### 📝 診断したい名前の情報を入力してください")
        st.caption("💡 「名前を生成」タブの結果から「💎 診断」を押すと、ここに自動入力されます。")

        eval_target = st.selectbox("命名の対象", ["人間（子供など）", "創作キャラクター", "企業・サービス・屋号", "ペット"])
        eval_wish = st.text_area("この名前に込めた想いや、想定する世界観（任意）", placeholder="例：誠実で信頼感のある会社にしたい、ファンタジー世界のエルフの騎士、など")

        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            eval_surname = st.text_input("苗字・前置き（任意）", key="eval_surname")
        with col_e2:
            eval_name = st.text_input("名前（必須）", key="eval_name")
        with col_e3:
            eval_yomi = st.text_input("読み仮名（必須）", key="eval_yomi")

        st.caption(f"残り診断回数：{remaining('eval')} 回（このセッション中）")

        if st.button("詳細評価レポートを作成する", type="primary"):
            if not eval_name or not eval_yomi:
                st.warning("「名前」と「読み仮名」は必ず入力してください。")
            elif check_limit("eval"):
                eval_prompt = f"""
                あなたは世界トップクラスのネーミングコンサルタント・言語学者です。
                ユーザーが考案した以下の名前を、プロの視点で多角的かつ厳密に診断してください。

                【診断対象】
                ・対象：{eval_target}
                ・苗字：{eval_surname}
                ・名前：{eval_name}
                ・読み：{eval_yomi}
                ・コンセプト/願い：{eval_wish}

                以下の要素を分析し、必ず以下のJSONフォーマットで出力してください。
                {{
                  "overall": {{
                    "score": 0〜100の総合点,
                    "rank": "S, A, B, C のいずれか",
                    "comment": "全体的な講評（2〜3文でプロ目線の鋭い評価）"
                  }},
                  "analysis": {{
                    "phonetic": "音韻心理学的な分析（母音や子音の響きが与える印象）",
                    "visual": "視覚的バランス・字形の印象（漢字や文字の並びの美しさ）"
                  }},
                  "global_risk": {{
                    "risk_level": "低, 中, 高 のいずれか",
                    "detail": "英語、中国語、その他の言語圏でネガティブな意味（スラング等）を持たないか、または特定の文化圏での文脈・ルーツに関する解説"
                  }},
                  "personas": [
                    {{"target": "若年層(10-20代)", "impression": "どのような印象を抱くか"}},
                    {{"target": "ビジネス層(30-50代)", "impression": "どのような印象を抱くか"}}
                  ],
                  "advice": "さらに名前を良くするための具体的な改善アドバイス",
                  "alternatives": [
                    {{"name": "提案1", "yomi": "ヨミ1", "reason": "改善理由"}},
                    {{"name": "提案2", "yomi": "ヨミ2", "reason": "改善理由"}}
                  ]
                }}
                """

                with st.spinner("🔍 専門的な視点で多角的に分析中..."):
                    try:
                        raw = cached_completion("gpt-4o", eval_prompt)
                        report = json.loads(raw)
                        count_usage("eval")

                        st.markdown("---")
                        st.markdown(f"## 📋 【{eval_surname} {eval_name}】 診断レポート")

                        rank = report["overall"]["rank"]
                        score = report["overall"]["score"]

                        col_r1, col_r2 = st.columns([1, 2])
                        with col_r1:
                            st.metric(label="🏆 総合スコア", value=f"{score} / 100", delta=f"ランク {rank}",
                                      delta_color="normal" if rank in ["S", "A"] else "inverse")
                        with col_r2:
                            st.info(f"**コンサルタント講評:**\n\n{report['overall']['comment']}")

                        st.markdown("### 🔍 1. 音韻と視覚の分析")
                        st.write(f"**🗣️ 音韻心理（響きの印象）:** {report['analysis']['phonetic']}")
                        st.write(f"**👁️ 視覚バランス（字形）:** {report['analysis']['visual']}")

                        st.markdown("### 🌍 2. グローバルリスク・文脈の裏付け")
                        risk = report["global_risk"]["risk_level"]
                        if risk == "低":
                            st.success(f"**【リスク：{risk}】** {report['global_risk']['detail']}")
                        elif risk == "中":
                            st.warning(f"**【リスク：{risk}】** {report['global_risk']['detail']}")
                        else:
                            st.error(f"**【リスク：{risk}】** {report['global_risk']['detail']}")

                        st.markdown("### 👥 3. ターゲット層別 受容度シミュレーション")
                        for p in report["personas"]:
                            st.markdown(f"- **{p['target']}:** {p['impression']}")

                        st.markdown("### 💡 4. プロフェッショナル・アドバイス")
                        st.write(report["advice"])

                        with st.expander("✨ コンサルタントからの代替案（微調整バージョン）を見る"):
                            for alt in report["alternatives"]:
                                st.code(f"{alt['name']} ({alt['yomi']})", language=None)
                                st.write(f"**理由:** {alt['reason']}")
                                st.markdown("---")

                    except Exception as e:
                        st.error(f"評価中にエラーが発生しました: {e}")

    elif user_password != "":
        st.error("コードが間違っています。")

# --------------------------------------------------
# 【タブ3】商標チェック ＋ ドメイン空きチェック
# --------------------------------------------------
with tab3:
    st.markdown("### 🔍 商標リスク 事前チェック")
    st.write("サービス名・商品名・屋号として使う前に、商標としてのリスクをAIが事前スクリーニングします。")

    st.warning(
        "⚠️ **このチェックはAIの知識に基づく事前スクリーニングであり、商標データベースとの照合結果ではありません。**\n\n"
        "正式な確認は特許庁の **J-PlatPat（特許情報プラットフォーム）** で必ず行ってください。"
        "出願を検討する場合は弁理士への相談を推奨します。"
    )

    st.caption("💡 「名前を生成」タブの結果から「🔍 商標」を押すと、ここに自動入力されます。")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        tm_name = st.text_input("チェックしたい名前（必須）", key="tm_name_input", placeholder="例：Namers AI")
    with col_t2:
        tm_yomi = st.text_input("読み仮名（任意・未入力ならAIが推定）", key="tm_yomi_input", placeholder="例：ネイマーズエーアイ")

    tm_classes = {
        "第9類：ソフトウェア・アプリ・電子機器": "9",
        "第28類：おもちゃ・ゲーム機・遊具": "28",
        "第35類：広告・マーケティング・小売": "35",
        "第41類：教育・エンタメ・ゲーム提供サービス": "41",
        "第42類：SaaS・IT開発・デザイン": "42",
        "第3類：化粧品・洗剤": "3",
        "第25類：被服・履物": "25",
        "第30類：菓子・パン・調味料": "30",
        "第43類：飲食店・宿泊": "43",
    }
    selected_classes = st.multiselect(
        "想定する用途（商標の区分）を選択", list(tm_classes.keys()),
        default=["第9類：ソフトウェア・アプリ・電子機器"],
        help="商標は「区分」ごとに登録されます。同じ名前でも区分が違えば共存できる場合があります。"
    )

    tm_check_btn = st.button("🛡️ 商標リスクをチェックする", use_container_width=True, type="primary")
    st.caption(f"残りチェック回数：{remaining('tm')} 回（このセッション中）")

    if tm_check_btn:
        if not tm_name:
            st.warning("チェックしたい名前を入力してください。")
        elif not selected_classes:
            st.warning("用途（区分）を1つ以上選択してください。")
        elif check_limit("tm"):
            tm_prompt = f"""
            あなたは商標実務に詳しいネーミングコンサルタントです。
            以下の名称について、商標登録の観点から「事前スクリーニング」を行ってください。

            【重要な制約】
            ・あなたは商標データベースにアクセスできません。あなたの知識の範囲内での分析であることを前提に、
              断定を避け、「可能性」「懸念」として表現してください。
            ・存在が不確かな商標や企業名を作り出さないでください。確実に知っている著名なもののみ挙げてください。

            【チェック対象】
            ・名称：{tm_name}
            ・読み：{tm_yomi if tm_yomi else "未入力（あなたが推定してください）"}
            ・想定区分：{", ".join(selected_classes)}

            【分析項目】
            1. 称呼（カタカナ読み）の確定と、類似と判断されやすい称呼バリエーションの展開
            2. 識別力の評価：一般名称的／記述的（商品の性質をそのまま説明している）／暗示的／造語 のどれに近いか。
               一般名称・記述的に近いほど、そもそも商標登録が認められにくいことを踏まえて評価すること。
            3. あなたが確実に知っている著名ブランド・有名商標との類似懸念（曖昧なものは挙げない）
            4. 選択された区分での競合の混み具合に関する一般的なコメント
            5. 総合リスクランク（低・中・高）と、その判断理由

            【出力形式（JSON）】
            必ず以下のJSONのみを出力してください。
            {{
              "shoko": "確定した称呼（カタカナ）",
              "romaji": "ローマ字表記",
              "similar_shoko": ["類似しやすい称呼1", "類似しやすい称呼2", "類似しやすい称呼3"],
              "distinctiveness": {{
                "type": "一般名称的 / 記述的 / 暗示的 / 造語 のいずれか",
                "comment": "識別力に関する評価コメント"
              }},
              "known_conflicts": [
                {{"name": "懸念のある著名ブランド名", "comment": "なぜ類似と判断される可能性があるか"}}
              ],
              "class_comment": "選択された区分での一般的な競合状況コメント",
              "risk_level": "低 / 中 / 高 のいずれか",
              "risk_reason": "総合リスクランクの判断理由（2〜3文）",
              "search_keywords": ["J-PlatPatで検索すべきキーワード1", "キーワード2", "キーワード3"]
            }}
            known_conflicts が思い当たらない場合は空のリスト [] にしてください。
            """

            with st.spinner("🛡️ 商標の観点から分析中..."):
                try:
                    raw = cached_completion("gpt-4o", tm_prompt)
                    tm_report = json.loads(raw)
                    count_usage("tm")

                    st.markdown("---")
                    st.markdown(f"## 🛡️ 【{tm_name}】 商標事前チェック結果")

                    risk = tm_report["risk_level"]
                    risk_msg = f"**【総合リスク：{risk}】** {tm_report['risk_reason']}"
                    if risk == "低":
                        st.success(risk_msg)
                    elif risk == "中":
                        st.warning(risk_msg)
                    else:
                        st.error(risk_msg)

                    st.markdown("### 🗣️ 1. 称呼（呼び方）の整理")
                    st.write("商標の類似判断では「称呼（呼び方）」が重視されます。以下の読み方で類似商標がないか確認してください。")
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.metric("称呼", tm_report["shoko"])
                    with col_s2:
                        st.metric("ローマ字", tm_report["romaji"])
                    st.write(f"**類似しやすい称呼:** {', '.join(tm_report['similar_shoko'])}")

                    st.markdown("### 🧩 2. 識別力（登録のされやすさ）")
                    st.write(f"**タイプ：{tm_report['distinctiveness']['type']}**")
                    st.write(tm_report["distinctiveness"]["comment"])

                    st.markdown("### ⚔️ 3. 著名ブランドとの類似懸念")
                    if tm_report["known_conflicts"]:
                        for c in tm_report["known_conflicts"]:
                            st.markdown(f"- **{c['name']}**：{c['comment']}")
                    else:
                        st.write("AIの知識の範囲では、著名ブランドとの明確な類似懸念は見つかりませんでした。"
                                 "（データベース照合ではないため、必ずJ-PlatPatで確認してください）")

                    st.write(f"**区分に関するコメント:** {tm_report['class_comment']}")

                    st.markdown("### ✅ 4. 次のステップ：J-PlatPatで正式に確認する")
                    st.write("以下のキーワードをコピーして、J-PlatPatの「商標検索」で照合してください。")
                    for kw in tm_report["search_keywords"]:
                        st.code(kw, language=None)

                    col_l1, col_l2 = st.columns(2)
                    with col_l1:
                        st.link_button("🏛️ J-PlatPat を開く（特許庁公式）",
                                       "https://www.j-platpat.inpit.go.jp/", use_container_width=True)
                    with col_l2:
                        st.link_button("🔎 Toreru商標検索 を開く（民間・無料）",
                                       "https://search.toreru.jp/", use_container_width=True)

                    st.caption("J-PlatPatでは「商標」→「商標検索」から、称呼（カタカナ）での検索が可能です。"
                               "選択した区分（類）を指定して絞り込むと精度が上がります。")

                    # 【改善1】ドメイン欄が空ならローマ字表記を自動セット（この時点ではまだ下のウィジェット未生成なので安全）
                    if not st.session_state.get("domain_base_input"):
                        st.session_state["domain_base_input"] = sanitize_domain_base(tm_report["romaji"])

                except Exception as e:
                    st.error(f"チェック中にエラーが発生しました: {e}")

    # ==================================================
    # 【改善1】ドメイン空きチェック（RDAPによる実照合）
    # ==================================================
    st.markdown("---")
    st.markdown("### 🌐 ドメイン空きチェック")
    st.write("こちらは商標と違い、**実際の登録データベース（RDAP）に問い合わせて確認**します。"
             "サービス名や屋号なら、商標と合わせてドメインの空きも確認しておくと安心です。")

    col_d1, col_d2 = st.columns([2, 3])
    with col_d1:
        domain_base = st.text_input("ドメインにしたい英字表記", key="domain_base_input",
                                    placeholder="例：namers-ai")
    with col_d2:
        tlds = st.multiselect(
            "確認するドメインの種類（TLD）",
            [".com", ".net", ".org", ".io", ".ai", ".app", ".dev", ".jp"],
            default=[".com", ".net", ".jp"]
        )

    dom_check_btn = st.button("🌐 ドメインの空きを確認する", use_container_width=True)
    st.caption(f"残り確認回数：{remaining('dom')} 回（このセッション中）")

    if dom_check_btn:
        cleaned = sanitize_domain_base(domain_base) if domain_base else ""
        if not cleaned:
            st.warning("英字表記を入力してください（使える文字：英小文字・数字・ハイフン）。")
        elif not tlds:
            st.warning("確認するドメインの種類を1つ以上選択してください。")
        elif check_limit("dom"):
            count_usage("dom")
            if cleaned != domain_base:
                st.caption(f"※ドメインに使えない文字を除去して「{cleaned}」として確認します。")

            st.markdown(f"#### 「{cleaned}」の確認結果")
            for tld in tlds:
                domain = f"{cleaned}{tld}"
                with st.spinner(f"{domain} を確認中..."):
                    status = check_domain_rdap(domain)
                if status == "available":
                    st.success(f"⭕ **{domain}** ：おそらく取得可能です（登録が見つかりませんでした）")
                elif status == "registered":
                    st.error(f"❌ **{domain}** ：すでに登録されています")
                else:
                    st.warning(f"❓ **{domain}** ：判定できませんでした（このドメイン種別はRDAP非対応の可能性があります）")

            st.caption(
                "※「取得可能」は問い合わせ時点での参考情報です。実際の取得はお名前.com・ムームードメイン等の"
                "登録サービスで最終確認してください。.jp はRDAP対応が不完全なため判定できない場合があります。"
            )

# --------------------------------------------------
# 【タブ4】お気に入りと履歴の管理
# --------------------------------------------------
with tab4:
    # 【改善9】データの保存範囲を最初に明示する
    st.info("📌 お気に入りと履歴は**ブラウザを閉じる（またはページを再読み込みする）と消えます**。"
            "残したいデータは下のCSV保存ボタンでダウンロードしてください。"
            "（Namers AIはログイン不要で使える代わりに、サーバーに個人データを保存しません）")

    st.markdown("### ⭐ お気に入りの名前")
    if st.session_state.favorites:
        # 【改善3】候補比較ビュー：お気に入りからレーダーチャートを重ねて比較
        if len(st.session_state.favorites) >= 2:
            with st.expander("📊 お気に入りを比較する（レーダーチャート重ね表示）", expanded=False):
                fav_names = [f["名前"] for f in st.session_state.favorites]
                compare_targets = st.multiselect("比較する名前を2〜3個選択", fav_names, max_selections=3)
                if len(compare_targets) >= 2:
                    selected_favs = [f for f in st.session_state.favorites if f["名前"] in compare_targets]
                    # 共通する判断軸だけで比較する（軸が違う生成同士でも比較できる範囲で）
                    common_axes = None
                    for f in selected_favs:
                        axes_set = set((f.get("軸スコア") or {}).keys())
                        common_axes = axes_set if common_axes is None else common_axes & axes_set
                    common_axes = sorted(common_axes) if common_axes else []

                    if len(common_axes) >= 3:
                        colors = ['#00CC96', '#636EFA', '#EF553B']
                        fig_cmp = go.Figure()
                        for idx, f in enumerate(selected_favs):
                            fig_cmp.add_trace(build_radar(common_axes, f["軸スコア"], f["名前"],
                                                          color=colors[idx % len(colors)]))
                        fig_cmp.update_layout(
                            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                            showlegend=True, height=350, margin=dict(t=30, b=30, l=40, r=40)
                        )
                        st.plotly_chart(fig_cmp, use_container_width=True, key="radar_compare")
                        st.caption(f"比較に使った判断軸：{', '.join(common_axes)}（選んだ名前に共通する軸のみ）")
                    else:
                        st.warning("選んだ名前同士で共通する判断軸が3つ未満のため比較できません。"
                                   "同じ判断軸の設定で生成した名前同士を選んでください。")

        for j, fav in enumerate(st.session_state.favorites):
            with st.container(border=True):
                col_f1, col_f2 = st.columns([3, 1])
                with col_f1:
                    st.code(f"{fav['名前']} ({fav['読み']})", language=None)
                    st.caption(f"総合点：{fav['総合点']}点｜追加：{fav['追加日時']}")
                    with st.expander("理由を見る"):
                        st.write(fav["理由"])
                with col_f2:
                    if st.button("🗑️ 削除", key=f"del_fav_{j}", use_container_width=True):
                        st.session_state.favorites.pop(j)
                        st.rerun()

        df_fav = pd.DataFrame([{k: v for k, v in f.items() if k not in ("軸スコア", "判断軸")}
                               for f in st.session_state.favorites])
        csv_fav = df_fav.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 お気に入りをCSVで保存", data=csv_fav,
                           file_name=f"favorites_{datetime.now().strftime('%Y%m%d')}.csv",
                           mime='text/csv', use_container_width=True)
    else:
        st.write("まだお気に入りはありません。「名前を生成」タブの結果から「⭐ 保存」を押すとここに保存されます。")

    st.markdown("---")
    st.markdown("### 📜 生成履歴")
    if st.session_state.generated_names:
        df_log = pd.DataFrame(st.session_state.generated_names)
        st.dataframe(df_log, use_container_width=True, hide_index=True)
        csv = df_log.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 履歴をCSVで保存", data=csv,
                           file_name=f"naming_log_{datetime.now().strftime('%Y%m%d')}.csv",
                           mime='text/csv', use_container_width=True)
    else:
        st.write("まだ生成履歴はありません。")

# =====================================================================
# タブの外（アプリ全体に共通して表示される部分）
# =====================================================================
st.markdown("---")
col_feedback1, col_feedback2 = st.columns([2, 1])
with col_feedback1:
    st.write("💡 アプリの改善にご協力ください！")
with col_feedback2:
    st.link_button("🧸アンケートに答える",
                   "https://docs.google.com/forms/d/e/1FAIpQLScEKP2qdJ49NgbjOrq27T4fDaPIXTqrUO74wdFMxMhtwdylPQ/viewform?usp=header",
                   use_container_width=True)
