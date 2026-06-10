# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス
import plotly.graph_objects as go  # グラフを描くためのライブラリ
import json   # JSONデータを扱うためのライブラリ
import base64 # 画像をテキストデータに変換するためのライブラリ

# =====================================================================
# ページ設定とデザイン（CSS）
# =====================================================================
st.set_page_config(page_title="Namers AI", page_icon="🪶", layout="centered")

# 軽量なカスタムCSS：カードの角丸・タブの視認性・ボタンの統一感
st.markdown("""
<style>
    /* タブのフォントを少し大きく、選択中を太字に */
    button[data-baseweb="tab"] p { font-size: 0.95rem; }
    button[data-baseweb="tab"][aria-selected="true"] p { font-weight: 700; }
    /* st.metric の数値を強調 */
    [data-testid="stMetricValue"] { font-size: 1.6rem; }
    /* コードブロック（名前コピー欄）の余白を詰める */
    [data-testid="stCode"] { margin-bottom: 0.3rem; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# セッション状態の初期化（アプリがリロードされるまで維持）
# =====================================================================
if 'generated_names' not in st.session_state:
    st.session_state.generated_names = []   # 生成履歴（CSV保存用）
if 'last_results' not in st.session_state:
    st.session_state.last_results = None    # 直近の生成結果（再描画用に保持）
if 'favorites' not in st.session_state:
    st.session_state.favorites = []         # お気に入りリスト

# --- タブ間連携用のコールバック関数 ---
def add_favorite(name, yomi, reason, score):
    """お気に入りに追加（重複は無視）"""
    entry = {"名前": name, "読み": yomi, "総合点": score, "理由": reason,
             "追加日時": datetime.now().strftime("%Y-%m-%d %H:%M")}
    if not any(f["名前"] == name for f in st.session_state.favorites):
        st.session_state.favorites.append(entry)

def send_to_trademark(name, yomi):
    """生成結果を商標チェックタブの入力欄へ転記"""
    st.session_state["tm_name_input"] = name
    st.session_state["tm_yomi_input"] = yomi
    st.toast(f"「{name}」を商標チェックタブにセットしました。タブを切り替えてください。", icon="🔍")

def send_to_eval(name, yomi):
    """生成結果をプレミアム評価タブの入力欄へ転記"""
    st.session_state["eval_name"] = name
    st.session_state["eval_yomi"] = yomi
    st.toast(f"「{name}」を詳細診断タブにセットしました。タブを切り替えてください。", icon="💎")

# タイトル
st.title("Namers AI　～AI名付け支援ツール～")
st.caption("名前の生成からプロ視点の診断、商標リスクの事前チェックまでを1つのアプリで。")

# OpenAIのクライアントを初期化
client = OpenAI()

# =====================================================================
# タブの作成：生成 / 評価 / 商標チェック / お気に入り・履歴
# =====================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "💡 名前を生成",
    "💎 詳細診断 (プレミアム)",
    "🔍 商標チェック",
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

    uploaded_file = st.file_uploader("📸 写真やイラストからイメージする（任意）", type=['png', 'jpg', 'jpeg'])
    submit_btn = st.button("✨ AIに名前を考えてもらう", use_container_width=True, type="primary")

    if submit_btn:
        if not wish and not uploaded_file and not selected_tags:
            st.warning("「雰囲気タグ」を選ぶか、「願い」の入力、または「画像」のアップロードをしてください！")
        else:
            image_data_url = None
            if uploaded_file:
                encoded_image = base64.b64encode(uploaded_file.read()).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{encoded_image}"
                st.info("📸 画像のイメージも考慮して名前を考えます！")

            surname_instruction = f"苗字は「{surname}」です。" if surname else "苗字はありません。"

            prompt = f"""
            あなたはプロの命名アドバイザーです。
            以下の条件に基づいて、最適な名前を3つ提案してください。

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
            以下の5項目（各100点満点）と、「総合得点（100点満点）」を厳密に採点してください。
            （響き、字形、独創、可読、願い）
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
                            "hibiki": 0〜100,
                            "jikei": 0〜100,
                            "doku": 0〜100,
                            "kadoku": 0〜100,
                            "negai": 0〜100
                        }},
                        "reason": "名前の語源・本来の意味を明記し、願いをどう叶えるか解説してください。"
                    }}
                ]
            }}
            """

            with st.spinner("💎 分析中..."):
                try:
                    if image_data_url:
                        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_data_url}}]}]
                    else:
                        messages = [{"role": "user", "content": prompt}]

                    response = client.chat.completions.create(
                        model="gpt-4o-mini", messages=messages, response_format={"type": "json_object"}
                    )

                    result_json = json.loads(response.choices[0].message.content)

                    # 結果をセッションに保存（ボタン操作で再実行されても結果が消えないようにする）
                    st.session_state.last_results = result_json["names"]

                    # 履歴にも追加
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

    # --- 生成結果の表示（セッションから描画するので、お気に入り追加などの操作後も消えない） ---
    if st.session_state.last_results:
        st.markdown("#### 🪶 提案された名前")
        for i, item in enumerate(st.session_state.last_results):
            name, yomi, reason, scores = item["name"], item["yomi"], item["reason"], item["scores"]
            s_total = scores.get("total", 80)

            categories = ['響き', '字形', '独創', '可読', '願い']
            values = [scores.get("hibiki", 50), scores.get("jikei", 50), scores.get("doku", 50),
                      scores.get("kadoku", 50), scores.get("negai", 50)]
            # レーダーチャートを閉じるために先頭の値を末尾に1回だけ追加
            values += [values[0]]
            categories += [categories[0]]

            fig = go.Figure(data=[go.Scatterpolar(r=values, theta=categories, fill='toself', name=name, line_color='#00CC96')])
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

                # 各候補へのアクションボタン（次の工程へワンタップで進める）
                b1, b2, b3 = st.columns(3)
                with b1:
                    st.button("⭐ お気に入り", key=f"fav_{i}", use_container_width=True,
                              on_click=add_favorite, args=(name, yomi, reason, s_total))
                with b2:
                    st.button("🔍 商標チェック", key=f"tm_{i}", use_container_width=True,
                              on_click=send_to_trademark, args=(name, yomi))
                with b3:
                    st.button("💎 詳細診断へ", key=f"ev_{i}", use_container_width=True,
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

    SECRET_CODE = "copenhagen"

    if user_password == SECRET_CODE:
        st.success("✅ 認証成功！プレミアム機能が解放されました。")

        st.markdown("#### 📝 診断したい名前の情報を入力してください")
        st.caption("💡 「名前を生成」タブの結果から「💎 詳細診断へ」を押すと、ここに自動入力されます。")

        eval_target = st.selectbox("命名の対象", ["人間（子供など）", "創作キャラクター", "企業・サービス・屋号", "ペット"])
        eval_wish = st.text_area("この名前に込めた想いや、想定する世界観（任意）", placeholder="例：誠実で信頼感のある会社にしたい、ファンタジー世界のエルフの騎士、など")

        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            eval_surname = st.text_input("苗字・前置き（任意）", key="eval_surname")
        with col_e2:
            eval_name = st.text_input("名前（必須）", key="eval_name")
        with col_e3:
            eval_yomi = st.text_input("読み仮名（必須）", key="eval_yomi")

        if st.button("詳細評価レポートを作成する", type="primary"):
            if not eval_name or not eval_yomi:
                st.warning("「名前」と「読み仮名」は必ず入力してください。")
            else:
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
                        eval_response = client.chat.completions.create(
                            model="gpt-4o",  # プレミアム機能なので精度の高いモデル(GPT-4o)を推奨
                            messages=[{"role": "user", "content": eval_prompt}],
                            response_format={"type": "json_object"}
                        )

                        report = json.loads(eval_response.choices[0].message.content)

                        # --- レポートのUI描画 ---
                        st.markdown("---")
                        st.markdown(f"## 📋 【{eval_surname} {eval_name}】 診断レポート")

                        # 1. 総合評価
                        rank = report["overall"]["rank"]
                        score = report["overall"]["score"]

                        col_r1, col_r2 = st.columns([1, 2])
                        with col_r1:
                            st.metric(label="🏆 総合スコア", value=f"{score} / 100", delta=f"ランク {rank}",
                                      delta_color="normal" if rank in ["S", "A"] else "inverse")
                        with col_r2:
                            st.info(f"**コンサルタント講評:**\n\n{report['overall']['comment']}")

                        # 2. 分析結果
                        st.markdown("### 🔍 1. 音韻と視覚の分析")
                        st.write(f"**🗣️ 音韻心理（響きの印象）:** {report['analysis']['phonetic']}")
                        st.write(f"**👁️ 視覚バランス（字形）:** {report['analysis']['visual']}")

                        # 3. リスク・文脈判定
                        st.markdown("### 🌍 2. グローバルリスク・文脈の裏付け")
                        risk = report["global_risk"]["risk_level"]
                        if risk == "低":
                            st.success(f"**【リスク：{risk}】** {report['global_risk']['detail']}")
                        elif risk == "中":
                            st.warning(f"**【リスク：{risk}】** {report['global_risk']['detail']}")
                        else:
                            st.error(f"**【リスク：{risk}】** {report['global_risk']['detail']}")

                        # 4. ペルソナシミュレーション
                        st.markdown("### 👥 3. ターゲット層別 受容度シミュレーション")
                        for p in report["personas"]:
                            st.markdown(f"- **{p['target']}:** {p['impression']}")

                        # 5. プロのアドバイスと代替案
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
# 【タブ3】新機能：商標チェック（AI事前スクリーニング + J-PlatPat導線）
# --------------------------------------------------
with tab3:
    st.markdown("### 🔍 商標リスク 事前チェック")
    st.write("サービス名・商品名・屋号として使う前に、商標としてのリスクをAIが事前スクリーニングします。")

    # 重要：これは「正式な商標調査」ではないことを最初に明示する
    st.warning(
        "⚠️ **このチェックはAIの知識に基づく事前スクリーニングであり、商標データベースとの照合結果ではありません。**\n\n"
        "正式な確認は特許庁の **J-PlatPat（特許情報プラットフォーム）** で必ず行ってください。"
        "出願を検討する場合は弁理士への相談を推奨します。"
    )

    st.caption("💡 「名前を生成」タブの結果から「🔍 商標チェック」を押すと、ここに自動入力されます。")

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        tm_name = st.text_input("チェックしたい名前（必須）", key="tm_name_input", placeholder="例：Namers AI")
    with col_t2:
        tm_yomi = st.text_input("読み仮名（任意・未入力ならAIが推定）", key="tm_yomi_input", placeholder="例：ネイマーズエーアイ")

    # 主要な商標区分（ニーズの高いものに絞って提示）
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

    if tm_check_btn:
        if not tm_name:
            st.warning("チェックしたい名前を入力してください。")
        elif not selected_classes:
            st.warning("用途（区分）を1つ以上選択してください。")
        else:
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
                    tm_response = client.chat.completions.create(
                        model="gpt-4o",  # 固有名詞の知識が重要なので精度の高いモデルを使用
                        messages=[{"role": "user", "content": tm_prompt}],
                        response_format={"type": "json_object"}
                    )

                    tm_report = json.loads(tm_response.choices[0].message.content)

                    st.markdown("---")
                    st.markdown(f"## 🛡️ 【{tm_name}】 商標事前チェック結果")

                    # 1. 総合リスク表示
                    risk = tm_report["risk_level"]
                    risk_msg = f"**【総合リスク：{risk}】** {tm_report['risk_reason']}"
                    if risk == "低":
                        st.success(risk_msg)
                    elif risk == "中":
                        st.warning(risk_msg)
                    else:
                        st.error(risk_msg)

                    # 2. 称呼の整理
                    st.markdown("### 🗣️ 1. 称呼（呼び方）の整理")
                    st.write("商標の類似判断では「称呼（呼び方）」が重視されます。以下の読み方で類似商標がないか確認してください。")
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.metric("称呼", tm_report["shoko"])
                    with col_s2:
                        st.metric("ローマ字", tm_report["romaji"])
                    st.write(f"**類似しやすい称呼:** {', '.join(tm_report['similar_shoko'])}")

                    # 3. 識別力
                    st.markdown("### 🧩 2. 識別力（登録のされやすさ）")
                    st.write(f"**タイプ：{tm_report['distinctiveness']['type']}**")
                    st.write(tm_report["distinctiveness"]["comment"])

                    # 4. 既知の類似懸念
                    st.markdown("### ⚔️ 3. 著名ブランドとの類似懸念")
                    if tm_report["known_conflicts"]:
                        for c in tm_report["known_conflicts"]:
                            st.markdown(f"- **{c['name']}**：{c['comment']}")
                    else:
                        st.write("AIの知識の範囲では、著名ブランドとの明確な類似懸念は見つかりませんでした。"
                                 "（データベース照合ではないため、必ずJ-PlatPatで確認してください）")

                    st.write(f"**区分に関するコメント:** {tm_report['class_comment']}")

                    # 5. J-PlatPatでの確認導線
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

                except Exception as e:
                    st.error(f"チェック中にエラーが発生しました: {e}")

# --------------------------------------------------
# 【タブ4】お気に入りと履歴の管理
# --------------------------------------------------
with tab4:
    st.markdown("### ⭐ お気に入りの名前")
    if st.session_state.favorites:
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

        # お気に入りのCSVダウンロード
        df_fav = pd.DataFrame(st.session_state.favorites)
        csv_fav = df_fav.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 お気に入りをCSVで保存", data=csv_fav,
                           file_name=f"favorites_{datetime.now().strftime('%Y%m%d')}.csv",
                           mime='text/csv', use_container_width=True)
    else:
        st.info("まだお気に入りはありません。「名前を生成」タブの結果から「⭐ お気に入り」を押すとここに保存されます。")

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
        st.info("まだ生成履歴はありません。")

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






































