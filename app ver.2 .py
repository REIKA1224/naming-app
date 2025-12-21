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
with st.expander("入力条件を開く", expanded=True):
    
    # --------------------------------------------------
    # 1. UI改善 & 苗字・詳細条件の入力
    # --------------------------------------------------
    st.markdown("### 📋 命名の条件")

    # ジャンル選択（横並びにする）
    target_type = st.radio("命名する対象", ["人間", "ペット", "キャラクター"], horizontal=True)

    # 苗字と性別を横並びにする
    col1, col2 = st.columns(2)
    with col1:
        surname = st.text_input("苗字（省略可）", placeholder="例：佐藤")
    with col2:
        gender = st.selectbox("性別", ["指定なし", "男", "女"])

    # 漢字数（スライダーをやめて、セレクトボックスに変更）
    kanji_count = st.selectbox("名前の漢字数", ["指定なし", "1文字", "2文字", "3文字"])

    # 使いたい漢字・避けたい漢字（横並びで見やすく）
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
# --------------------------------------------------
# 2. プロンプト（AIへの指示）の実行と表示
# --------------------------------------------------
if submit_btn:
    if not wish:
        st.warning("「願い」を入力してください！")
    else:
        # 苗字がある場合とない場合でメッセージを変える
        surname_text = f"苗字「{surname}」" if surname else "苗字なし"

        # プロンプト作成
        prompt = f"""
        あなたは辛口かつ的確なプロの命名アドバイザーです。
        以下の条件に基づいて、名前を3つ提案してください。
        
        【重要：評価システム】
        提案する名前と{surname_text}の組み合わせについて、以下の3項目で厳密に採点（各100点満点）し、
        その平均を「総合点」として算出してください。
        AIが考えた名前だからといって満点にせず、客観的に評価してください。

        1. 【語呂】苗字とつなげて呼んだ時のリズム、言いやすさ
        2. 【字面】漢字の並びの美しさ、画数のバランス
        3. 【独創性】ありきたりすぎず、かつキラキラネームすぎないか

        【重要】
        出力時は「**」などの太字記号や見出し記号（###）は一切使わず、
        普通のテキストだけで出力してください。

        【条件】
        ・対象：{target_type}
        ・性別：{gender}
        ・漢字数：{kanji_count}
        ・使いたい漢字：{use_kanji}
        ・避けたい漢字：{avoid_kanji}
        ・願い：{wish}
        
        【出力形式】
        必ず以下の形式で出力すること。

        ---
        名前：〇〇（ヨミ）
        総合ランク：A（88点）
        [内訳]
        ・語呂：90点
        ・字面：85点
        ・独創性：89点
        
        理由：〜〜〜
        ---
        """

        # AIに問い合わせ
        with st.spinner("💎 厳密な基準で選定・採点中..."):
            try:
                # API呼び出し
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # AIの返事を受け取る
                response_content = response.choices[0].message.content

                # 結果表示
                # 結果表示
                st.success("命名案が完成しました！")
                st.markdown("### 📝 提案結果と分析")

                # AIの回答を「---」で区切って、ひとつずつ処理する
                # （AIが複数の候補を出してくるため）
                sections = response_content.split('---')

                for section in sections:
                    # 空っぽのセクションは飛ばす
                    if "名前：" not in section:
                        continue
                    
                    # ------------------------------------------------
                    # 1. 正規表現で「名前」と「各点数」を抜き出す
                    # ------------------------------------------------
                    name_match = re.search(r"名前：(.*?)\n", section)
                    goro_match = re.search(r"語呂：(\d+)点", section)
                    jimen_match = re.search(r"字面：(\d+)点", section)
                    doku_match = re.search(r"独創性：(\d+)点", section)

                    # 名前が見つかったら表示処理スタート
                    if name_match:
                        name = name_match.group(1).strip()
                        
                        # 点数が取れたら数字に変換、取れなかったら0点にする（エラー防止）
                        score_goro = int(goro_match.group(1)) if goro_match else 0
                        score_jimen = int(jimen_match.group(1)) if jimen_match else 0
                        score_doku = int(doku_match.group(1)) if doku_match else 0
                        
                        # ------------------------------------------------
                        # 2. レーダーチャートを作成（Plotly）
                        # ------------------------------------------------
                        categories = ['語呂', '字面', '独創性']
                        values = [score_goro, score_jimen, score_doku]
                        
                        # グラフのデータを閉じるために、最初の値を最後にもう一度入れる
                        values += [values[0]]
                        categories += [categories[0]]

                        fig = go.Figure(
                            data=[
                                go.Scatterpolar(
                                    r=values,
                                    theta=categories,
                                    fill='toself',
                                    name=name,
                                    line_color='#1E90FF' # 水色
                                )
                            ]
                        )

                        # グラフのデザイン調整
                        fig.update_layout(
                            polar=dict(
                                radialaxis=dict(
                                    visible=True,
                                    range=[0, 100] # 0点〜100点の範囲
                                )
                            ),
                            showlegend=False,
                            height=300, # グラフの高さ
                            margin=dict(t=30, b=30, l=30, r=30) # 余白
                        )

                        # ------------------------------------------------
                        # 3. 画面に表示（左に文字、右にグラフ）
                        # ------------------------------------------------
                        with st.container(border=True):
                            col_text, col_graph = st.columns([3, 2])
                            
                            with col_text:
                                # 名前を大きく表示
                                st.markdown(f"### {name}")
                                # 説明文を表示（改行ズレ対策済み）
                                st.markdown(section.replace("\n", "  \n"))
                            
                            with col_graph:
                                # 作ったグラフを表示
                                st.plotly_chart(fig, use_container_width=True)

                # ------------------------------
                # 生成結果をCSVに保存
                # ------------------------------
                df = pd.DataFrame([[
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    target_type,
                    gender,
                    kanji_count,
                    use_kanji,
                    avoid_kanji,
                    wish,
                    response_content
                ]], columns=["timestamp", "対象", "性別", "漢字数", "使いたい漢字", "避けたい漢字", "願い", "生成候補"])

                filename = f"names_api_{datetime.now().strftime('%Y%m%d')}.csv"
                df.to_csv(filename, index=False, mode="a", header=False, encoding="utf-8-sig")
                
                st.caption(f"※結果は自動的に {filename} に保存されました")
            
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

# ------------------------------
# 評価アンケートへのリンクを表示
# ------------------------------
st.markdown("---")  # 区切り線を表示
st.markdown("### 評価アンケートはこちら")
st.markdown("[👉 Googleフォームで評価する](https://www.amazon.co.jp/)")





































