
# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス
import plotly.graph_objects as go  # グラフを描くためのライブラリ
import re                          # 文字の中から数字を抜き出すためのライブラリ
import json   # JSONデータを扱うためのライブラリ（追加）
import base64 # 画像をテキストデータに変換するためのライブラリ（追加）

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

# 画像アップロード機能の下にあるはずです
uploaded_file = st.file_uploader("📸 写真やイラストからイメージする（任意）", type=['png', 'jpg', 'jpeg'])
submit_btn = st.button("✨ AIに名前を考えてもらう", use_container_width=True, type="primary") # ← こっちは残す

# --------------------------------------------------
# 2. プロンプト（AIへの指示）と生成処理
# --------------------------------------------------
if submit_btn:
    if not wish and not uploaded_file: # 画像も願いもなければ警告
        st.warning("「願い」を入力するか、「画像」をアップロードしてください！")
    else:
        # -------------------------------------------------------
        # 画像の処理（Base64エンコード）
        # -------------------------------------------------------
        image_data_url = None
        if uploaded_file:
            # 画像を読み込んでBase64文字列に変換
            encoded_image = base64.b64encode(uploaded_file.read()).decode('utf-8')
            image_data_url = f"data:image/jpeg;base64,{encoded_image}"
            st.info("📸 画像のイメージも考慮して名前を考えます！")

        # -------------------------------------------------------
        # プロンプト定義：JSON形式を強制（追加機能 1）
        # -------------------------------------------------------
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
        ・願い・特徴：{wish}
        ※画像が提供されている場合は、その視覚的イメージ（色、雰囲気、モチーフ）も強く反映してください。

        【出力形式（JSON）】
        必ず以下のJSONフォーマットのみを出力してください。余計な文章は不要です。
        
        {{
            "names": [
                {{
                    "name": "名前の表記（例：大翔）",
                    "yomi": "読み仮名（例：ヒロト）",
                    "scores": {{
                        "hibiki": 0〜100の整数,
                        "jikei": 0〜100の整数,
                        "doku": 0〜100の整数,
                        "kadoku": 0〜100の整数,
                        "negai": 0〜100の整数
                    }},
                    "reason": "命名の理由（100文字程度）"
                }},
                ...（計3つ）
            ]
        }}
        """

        # -------------------------------------------------------
        # API呼び出し
        # -------------------------------------------------------
        with st.spinner("💎 分析中..."):
            try:
                # メッセージの構築（画像がある場合とない場合で分ける）
                messages = []
                if image_data_url:
                    # 画像ありモード（マルチモーダル）
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
                    # テキストのみモード
                    messages = [{"role": "user", "content": prompt}]

                # APIリクエスト（JSONモードを有効化）
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    response_format={"type": "json_object"}  # ★ここが重要！
                )
                
                # JSONとして結果を読み込む（正規表現はもう不要です！）
                result_json = json.loads(response.choices[0].message.content)
                name_list = result_json["names"] # リストを取得

                st.success("生成が完了しました！")

                # -------------------------------------------------------
                # 結果の表示ループ
                # -------------------------------------------------------
                for item in name_list:
                    name = item["name"]
                    yomi = item["yomi"]
                    reason = item["reason"]
                    scores = item["scores"]

                    # レーダーチャート作成
                    categories = ['響き', '字形', '独創', '可読', '願い']
                    values = [
                        scores["hibiki"], scores["jikei"], scores["doku"], 
                        scores["kadoku"], scores["negai"]
                    ]
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

                    # UI表示
                    with st.container(border=True):
                        col_text, col_graph = st.columns([1.2, 1])
                        with col_text:
                            # 追加機能 5: コピーしやすいように st.code を使用
                            st.caption("名前（コピーできます👇）")
                            st.code(f"{name} ({yomi})", language=None)
                            
                            st.markdown(f"**理由**")
                            st.write(reason)
                        
                        with col_graph:
                            st.plotly_chart(fig, use_container_width=True)

                    # 履歴保存用のデータ作成
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
# ダウンロードボタン
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






























































