# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス
import plotly.graph_objects as go  # グラフを描くためのライブラリ
import re                          # 文字の中から数字を抜き出すためのライブラリ
import json   # JSONデータを扱うためのライブラリ
import base64 # 画像をテキストデータに変換するためのライブラリ

# セッション状態でデータを保持（アプリがリロードされるまで維持）
if 'generated_names' not in st.session_state:
    st.session_state.generated_names = []

# タイトル
st.title("Namers AI　～AI名付け支援ツール～")

# OpenAIのクライアントを初期化
client = OpenAI()

# =====================================================================
# 👇 ここで画面を「無料（生成）」と「有料（評価）」の2つのタブに分けます
# =====================================================================
tab1, tab2 = st.tabs(["💡 名前を生成する (無料)", "💎 候補を評価する (プレミアム)"])

# --------------------------------------------------
# 【タブ1】既存の名前生成機能
# --------------------------------------------------
with tab1:
    # ------------------------------
    # 入力フォーム
    # ------------------------------    
    with st.expander("👇 入力条件を開く（ここをタップ）", expanded=True):
        
        st.markdown("### 📋 名付けの条件")

        # ジャンル選択
        target_type = st.radio("名付けする対象", ["人間", "ペット", "キャラクター"], horizontal=True)

        # 苗字と性別
        col1, col2 = st.columns(2)
        with col1:
            surname = st.text_input("苗字（省略可）", placeholder="例：佐藤")
        with col2:
            gender = st.selectbox("性別", ["指定なし", "男", "女"])

        # 使いたい漢字・避けたい漢字
        col3, col4 = st.columns(2)
        with col3:
            use_kanji = st.text_input("使いたい漢字（省略可）", placeholder="例：翔、愛")
        with col4:
            avoid_kanji = st.text_input("避けたい漢字(省略可）", placeholder="例：悪、死")

        # カテゴリ別タグ選択
        st.markdown("##### 💡 どんな名前にしたい？（カテゴリから選択）")
        
        tag_categories = {
            "基本のイメージ": ["明るい", "元気", "優しい", "クール", "知的", "上品","美しい", "かっこいい", "可愛い"],
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
                    f"{category_name}を選択",
                    tags_list,
                    selection_mode="multi",
                    key=f"tag_{category_name}",
                    label_visibility="collapsed"
                )
                if selections:
                    selected_tags.extend(selections)

        if selected_tags:
            st.caption(f"選択中: {', '.join(selected_tags)}")
        
        tags = selected_tags 
        wish = st.text_area("その他の願い・詳細（任意）", placeholder="例：春生まれなので、温かいイメージを入れたい")

    uploaded_file = st.file_uploader("📸 写真やイラストからイメージする（任意）", type=['png', 'jpg', 'jpeg'])
    submit_btn = st.button("✨ AIに名前を考えてもらう", use_container_width=True, type="primary")

    # --------------------------------------------------
    # プロンプト（AIへの指示）と生成処理
    # --------------------------------------------------
    if submit_btn:
        if not wish and not uploaded_file:
            st.warning("「願い」を入力するか、「画像」をアップロードしてください！")
        else:
            image_data_url = None
            if uploaded_file:
                encoded_image = base64.b64encode(uploaded_file.read()).decode('utf-8')
                image_data_url = f"data:image/jpeg;base64,{encoded_image}"
                st.info("📸 画像のイメージも考慮して名前を考えます！")

            if surname:
                surname_instruction = f"苗字は「{surname}」です。"
            else:
                surname_instruction = "苗字はありません。"

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
            ユーザーの「願い」や「対象」の中に、**特定の国籍や地域（インド、フランス、中国など）の指定がある場合**は、以下のルールを無視して、その国の文化に合った名前（基本はカタカナ、中国なら漢字）を最優先で提案してください。

            国籍指定がない場合は、以下の基準で判断してください：
            1. 苗字が「カタカナ」の場合：下の名前も「カタカナ」
            2. 苗字が「漢字」の場合：基本は「漢字」
            3. 苗字なし・ファンタジー：世界観に合わせて自由選択

            【重要：評価システム】
            以下の5項目で厳密に採点（各100点満点）してください。また、その評価は名前ごとに特徴をはっきりさせるために厳しめに評価してください。
            （響き、字形、独創、可読、願い）

            【出力形式（JSON）】
            必ず以下のJSONフォーマットのみを出力してください。
            {{
                "names": [
                    {{
                        "name": "名前の表記",
                        "yomi": "読み仮名",
                        "scores": {{
                            "hibiki": 0〜100,
                            "jikei": 0〜100,
                            "doku": 0〜100,
                            "kadoku": 0〜100,
                            "negai": 0〜100
                        }},
                        "reason": "【必須】名前の『語源・本来の意味』（例：ドイツ語で『高貴な光』を意味するAlinaに由来）を明記し、それがユーザーの願い（{wish}）をどう叶えるかを具体的に解説してください。"
                    }}
                ]
            }}
            """

            with st.spinner("💎 分析中..."):
                try:
                    messages = []
                    if image_data_url:
                        messages = [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": image_data_url}}
                                ]
                            }
                        ]
                    else:
                        messages = [{"role": "user", "content": prompt}]

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        response_format={"type": "json_object"}
                    )
                    
                    result_json = json.loads(response.choices[0].message.content)
                    name_list = result_json["names"]

                    st.success("生成が完了しました！")

                    for item in name_list:
                        name = item["name"]
                        yomi = item["yomi"]
                        reason = item["reason"]
                        scores = item["scores"]

                        s_hibiki = scores.get("hibiki", scores.get("響き", 50))
                        s_jikei  = scores.get("jikei",  scores.get("字形", 50))
                        s_doku   = scores.get("doku",   scores.get("独創", 50))
                        s_kadoku = scores.get("kadoku", scores.get("可読", 50))
                        s_negai  = scores.get("negai",  scores.get("願い", 50))

                        categories = ['響き', '字形', '独創', '可読', '願い']
                        values = [s_hibiki, s_jikei, s_doku, s_kadoku, s_negai]
                        
                        values += [values[0]]
                        categories += [categories[0]]
                        values += [values[0]]
                        categories += [categories[0]]

                        fig = go.Figure(
                            data=[
                                go.Scatterpolar(
                                    r=values, theta=categories, fill='toself', name=name, line_color='#00CC96'
                                )
                            ]
                        )
                        fig.update_layout(
                            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                            showlegend=False, height=250, margin=dict(t=20, b=20, l=30, r=30)
                        )

                        with st.container(border=True):
                            col_text, col_graph = st.columns([1.2, 1])
                            with col_text:
                                st.caption("名前（コピーできます👇）")
                                st.code(f"{name} ({yomi})", language=None)
                                st.markdown(f"**理由**")
                                st.write(reason)
                            
                            with col_graph:
                                st.plotly_chart(fig, use_container_width=True)

                        current_data = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "対象": target_type,
                            "名前": f"{name} ({yomi})",
                            "理由": reason
                        }
                        st.session_state.generated_names.append(current_data)

                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

# --------------------------------------------------
# 【タブ2】新機能：プレミアム評価レポート（noteパスワード式）
# --------------------------------------------------
with tab2:
    st.markdown("### 💎 プレミアム詳細評価レポート")
    st.write("ご自身で考えた名前や、最終候補に残った名前を多角的に分析し、客観的なリスクや印象を評価する専用モードです。（現在は試作段階のためコードは無料公開中です）")
    
    # noteなどのURLを入れる場所（ご自身のnoteのURLに書き換えてください）
    note_url = "https://note.com/namersai/n/nd1fda095acbc?sub_rt=share_pb"
    
    with st.container(border=True):
        st.markdown("🔒 **この機能を利用するにはアクセスコードが必要です。**")
        col_input, col_link = st.columns([2, 1])
        
        with col_input:
            user_password = st.text_input("アクセスコードを入力", type="password", placeholder="例：namers2026")
        
        with col_link:
            st.write("") # 高さ調整
            st.write("")
            st.link_button("コードを取得(noteへ)", note_url, use_container_width=True)

    # パスワード判定（ここでは仮に namers2026 としています）
    SECRET_CODE = "copenhagen"
    
    if user_password == SECRET_CODE:
        st.success("✅ 認証成功！プレミアム機能が解放されました。")
        
        # -----------------------------------------
        # ここに評価機能のUIを配置（例）
        # -----------------------------------------
        st.markdown("#### 📝 評価したい名前を入力してください")
        eval_surname = st.text_input("苗字", key="eval_surname")
        eval_name = st.text_input("名前", key="eval_name")
        eval_yomi = st.text_input("読み仮名", key="eval_yomi")
        
        if st.button("詳細評価レポートを作成する", type="primary"):
            if eval_name:
                st.info("ここにAIによる詳細な分析レポート（音韻心理分析、グローバルリスク判定など）が出力されます。（※現在はモックアップです）")
            else:
                st.warning("評価したい名前を入力してください。")
                
    elif user_password != "":
        st.error("コードが間違っています。")

# =====================================================================
# タブの外（アプリ全体に共通して表示される部分）
# =====================================================================

# 履歴ダウンロードボタン（サイドバー）
if st.session_state.generated_names:
    df_log = pd.DataFrame(st.session_state.generated_names)
    csv = df_log.to_csv(index=False).encode('utf-8-sig')
    
    st.sidebar.markdown("### 履歴管理")
    st.sidebar.download_button(
        label="📥 履歴をCSVで保存",
        data=csv,
        file_name=f"naming_log_{datetime.now().strftime('%Y%m%d')}.csv",
        mime='text/csv',
    )

# アンケートリンク（一番下）
st.markdown("---")
col_feedback1, col_feedback2 = st.columns([2, 1])

with col_feedback1:
    st.write("💡 アプリの改善にご協力ください！")

with col_feedback2:
    st.link_button(
        label="🧸アンケートに答える",
        url="https://docs.google.com/forms/d/e/1FAIpQLScEKP2qdJ49NgbjOrq27T4fDaPIXTqrUO74wdFMxMhtwdylPQ/viewform?usp=header",
        use_container_width=True
    )






































































