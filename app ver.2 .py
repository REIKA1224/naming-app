# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス
import plotly.graph_objects as go  # グラフを描くためのライブラリ
import re                          # 文字の中から数字を抜き出すためのライブラリ

# その下にタイトル
st.title("AI 命名支援ツール")


# OpenAIのクライアントを初期化
client = OpenAI()

# ------------------------------
# 入力フォーム
# -----------------------------    
# サイドバーではなく、メイン画面上部に折りたたみメニューとして配置
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
# 2. プロンプト（AIへの指示）の変更
# --------------------------------------------------
if submit_btn:
    if not wish:
        st.warning("「願い」を入力してください！")
    else:
        # 苗字の有無で指示を変える
        if surname:
            surname_instruction = f"【重要】苗字は必ず入力された「{surname}」を使用してください。勝手に別の苗字を作ったりしないでください。"
        else:
            surname_instruction = "苗字は入力されていないため、下の名前のみを提案してください。"

        # -------------------------------------------------------
        # プロンプト：外国姓（カタカナ）の対応ルールを追加
        # -------------------------------------------------------
        prompt = f"""
        あなたはプロの命名アドバイザーです。
        以下の条件に基づいて、最適な名前を3つ提案してください。

        【重要：苗字の扱い】
        {surname_instruction}

        【最重要：文字種（漢字・カタカナ）の判断基準】
        入力された「苗字」と「願い（世界観）」を見て、名前の文字種を自動で切り替えてください。

        1. **苗字が「カタカナ」の場合（例：マードック）**
           - **下の名前も「カタカナ」にしてください。**
           - 例：マードック・マット、マードック・ハーヴィー
           - ※無理に漢字を使わないでください。

        2. **苗字が「漢字」の場合（例：佐藤）**
           - 基本は「漢字」の名前を提案してください。
           - 「アメリカ人風」等の指定がある場合のみ、「ジョージ（譲治）」のような当て字、またはカタカナを提案してください。

        3. **苗字なし・ファンタジーの場合**
           - 世界観に合わせて自由にカタカナ・漢字を選んでください。

        【重要：評価システム】
        以下の5項目で厳密に採点（各100点満点）してください。
        全てを高得点にせず、メリハリをつけてください。

        1. 【響き】呼んだ時のリズム、苗字との語呂（外国名ならその国らしい響きか）
        2. 【字形】文字の並びの美しさ（カタカナならバランス）
        3. 【独創】ユニークさ、被りにくさ
        4. 【可読】誰でも読めるか
        5. 【願い】ユーザーの願い（国籍や職業の設定）と合致しているか

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
        必ず以下の形式で出力すること。
        （外国名の場合、名前の間の「・」や半角スペースは自然に入れてください）

        ---
        名前：{surname if surname else ""} 〇〇（ヨミ）
        [内訳]
        ・響き：80点
        ・字形：90点
        ・独創：95点
        ・可読：60点
        ・願い：100点
        
        理由：〜〜〜
        ---
        """

        with st.spinner("💎 苗字と世界観に合わせて分析中..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                response_content = response.choices[0].message.content
                st.success("分析が完了しました！")

                # 結果表示処理
                sections = response_content.split('---')

                for section in sections:
                    if "名前：" not in section:
                        continue
                    
                    # 5つの項目を取得
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
                        
                        # 五角形のレーダーチャートを作成
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

                        # 表示
                        with st.container(border=True):
                            col_text, col_graph = st.columns([1, 1])
                            with col_text:
                                st.markdown(f"### {name}")
                                st.markdown(section.replace("\n", "  \n"))
                            with col_graph:
                                st.plotly_chart(fig, use_container_width=True)

                # CSV保存処理
                df = pd.DataFrame([[
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    target_type, gender, use_kanji, avoid_kanji, wish, response_content
                ]], columns=["timestamp", "対象", "性別", "使いたい漢字", "避けたい漢字", "願い", "生成候補"])
                
                filename = f"names_api_{datetime.now().strftime('%Y%m%d')}.csv"
                df.to_csv(filename, index=False, mode="a", header=False, encoding="utf-8-sig")

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
# ------------------------------
# 評価アンケートへのリンクを表示
# ------------------------------
st.markdown("---")  # 区切り線を表示
st.markdown("### 評価アンケートはこちら")
st.markdown("[👉 Googleフォームで評価する](https://www.amazon.co.jp/)")















































