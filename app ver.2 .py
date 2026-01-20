
# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス
import plotly.graph_objects as go  # グラフを描くためのライブラリ
import re                          # 文字の中から数字を抜き出すためのライブラリ

# セッション状態でデータを保持（アプリがリロードされるまで維持）
if 'generated_names' not in st.session_state:
    st.session_state.generated_names = []

# その下にタイトル
st.title("AI 命名支援ツール")


# OpenAIのクライアントを初期化
client = OpenAI()

# ------------------------------
# 入力フォーム
# ------------------------------    
with st.expander("👇 入力条件を開く（ここをタップ）", expanded=True):
    
    st.markdown("### 📋 命名の条件")

    # ジャンル選択
    target_type = st.radio("命名する対象", ["人間", "ペット", "キャラクター"], horizontal=True)

    # 苗字と性別
    col1, col2 = st.columns(2)
    with col1:
        surname = st.text_input("苗字（省略可）", placeholder="例：佐藤")
    with col2:
        gender = st.selectbox("性別", ["指定なし", "男", "女"])

    # ★ここに「漢字数」がありましたが、削除しました

    # 使いたい漢字・避けたい漢字
    col3, col4 = st.columns(2)
    with col3:
        use_kanji = st.text_input("使いたい漢字", placeholder="例：翔、愛")
    with col4:
        avoid_kanji = st.text_input("避けたい漢字", placeholder="例：悪、死")

    # 願いの入力
    wish = st.text_area("どんな願いを込めますか？", placeholder="例：優しくて芯の強い子に育ってほしい")

    # 生成ボタン
    submit_btn = st.button("✨ AIに名前を考えてもらう", use_container_width=True, type="primary")
# --------------------------------------------------
# 2. プロンプト（AIへの指示）と生成処理
# --------------------------------------------------
if submit_btn:
    if not wish:
        st.warning("「願い」を入力してください！")
    else:
        # 苗字の有無で指示を変える
        if surname:
            surname_instruction = f"【重要】苗字は「{surname}」です。この苗字とつなげた時の響きが良い名前を考えてください。"
        else:
            surname_instruction = "苗字は入力されていないため、下の名前のみを提案してください。"

        # -------------------------------------------------------
        # プロンプト定義（ここが消えていたのが原因です）
        # -------------------------------------------------------
        prompt = f"""
        あなたはプロの命名アドバイザーです。
        以下の条件に基づいて、最適な名前を3つ提案してください。

        【重要：苗字の扱い】
        {surname_instruction}

        【最重要：文字種（漢字・カタカナ）の判断基準】
        入力された「苗字」と「願い（世界観）」を見て、名前の文字種を自動で切り替えてください。
        1. 苗字が「カタカナ」の場合：下の名前も「カタカナ」
        2. 苗字が「漢字」の場合：基本は「漢字」。「アメリカ人風」等の指定があればカタカナも可。
        3. 苗字なし・ファンタジー：世界観に合わせて自由選択

        【重要：評価システム】
        以下の5項目で厳密に採点（各100点満点）してください。
        **「響き」の点数は、苗字（{surname}）とつなげた時のリズムで採点**してください。
        （ただし、出力する文字には苗字を含めないでください）

        1. 【響き】呼んだ時のリズム、苗字との語呂
        2. 【字形】文字の並びの美しさ
        3. 【独創】ユニークさ、被りにくさ
        4. 【可読】誰でも読めるか
        5. 【願い】ユーザーの願いと合致しているか

        【重要】
        出力時は「**」などの太字記号や見出し記号（###）は一切使わず、
        普通のテキストだけで出力してください。

        【条件】
        ・対象：{target_type}
        ・性別：{gender}
        ・使いたい漢字：{use_kanji}
        ・避けたい漢字：{avoid_kanji}
        ・願い：{wish}
        
        【出力形式】
        **苗字は含めず、下の名前のみ**を出力してください。

        ---
        名前：〇〇（ヨミ）
        [内訳]
        ・響き：80点
        ・字形：90点
        ・独創：95点
        ・可読：60点
        ・願い：100点
        
        理由：〜〜〜
        ---
        """

        # -------------------------------------------------------
        # API呼び出しと表示処理
        # -------------------------------------------------------
        with st.spinner("💎 苗字と世界観に合わせて分析中..."):
            try:
                # API呼び出し
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                response_content = response.choices[0].message.content
                st.success("分析が完了しました！")

                # 結果を分割して処理
                sections = response_content.split('---')

                for section in sections:
                    if "名前：" not in section:
                        continue
                    
                    # 採点スコアの取得関数
                    def get_score(pattern, text):
                        match = re.search(pattern, text)
                        return int(match.group(1)) if match else 50

                    s_hibiki = get_score(r"響き：(\d+)点", section)
                    s_jikei  = get_score(r"字形：(\d+)点", section)
                    s_doku   = get_score(r"独創：(\d+)点", section)
                    s_kadoku = get_score(r"可読：(\d+)点", section)
                    s_negai  = get_score(r"願い：(\d+)点", section)

                    name_match = re.search(r"名前：(.*?)\n", section)
                    if name_match:
                        name = name_match.group(1).strip()
                        
                        # レーダーチャート作成
                        categories = ['響き', '字形', '独創', '可読', '願い']
                        values = [s_hibiki, s_jikei, s_doku, s_kadoku, s_negai]
                        values += [values[0]]
                        categories += [categories[0]]

                        fig = go.Figure(
                            data=[
                                go.Scatterpolar(
                                    r=values,
                                    theta=categories,
                                    fill='toself',
                                    name=name,
                                    line_color='#00CC96'
                                )
                            ]
                        )

                        fig.update_layout(
                            polar=dict(
                                radialaxis=dict(visible=True, range=[0, 100])
                            ),
                            showlegend=False,
                            height=300,
                            margin=dict(t=30, b=30, l=40, r=40)
                        )

                        # 画面表示
                        with st.container(border=True):
                            col_text, col_graph = st.columns([1, 1])
                            with col_text:
                                st.markdown(f"### {name}")
                                st.markdown(section.replace("\n", "  \n"))
                            with col_graph:
                                st.plotly_chart(fig, use_container_width=True)

                        # ★履歴データの保存（インデント修正済み）
                        current_data = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "対象": target_type,
                            "名前": name,
                            "生成候補": section
                        }
                        st.session_state.generated_names.append(current_data)

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

# --------------------------------------------------
# ダウンロードボタンの表示（if submit_btnの外側）
# --------------------------------------------------
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
# ------------------------------
# 評価アンケートへのリンクを表示
# ------------------------------
st.markdown("---")  # 区切り線を表示
st.markdown("### 評価アンケートはこちら")
st.markdown("[👉 Googleフォームで評価する](https://www.amazon.co.jp/)")



























































