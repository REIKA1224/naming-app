# ライブラリのインポート
import streamlit as st          # Webアプリを作るためのフレームワーク
import pandas as pd             # 表形式データ（DataFrame）を扱うライブラリ。CSV保存に使用
from datetime import datetime   # 日付・時刻を扱う標準ライブラリ
from openai import OpenAI       # OpenAIのAPIを利用するためのクラス
import plotly.graph_objects as go  # グラフを描くためのライブラリ
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
# タブの作成：「無料（生成）」と「有料（評価）」
# =====================================================================
tab1, tab2 = st.tabs(["💡 名前を生成する (無料)", "💎 候補を評価する (プレミアム)"])

# --------------------------------------------------
# 【タブ1】既存の名前生成機能
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
        if not wish and not uploaded_file:
            st.warning("「願い」を入力するか、「画像」をアップロードしてください！")
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
            特定の国籍や地域の指定がある場合は、文化に合った名前を最優先で提案してください。
            指定がない場合：苗字がカタカナなら下もカタカナ、漢字なら漢字、ファンタジーは自由。

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
                    messages = []
                    if image_data_url:
                        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_data_url}}]}]
                    else:
                        messages = [{"role": "user", "content": prompt}]

                    response = client.chat.completions.create(
                        model="gpt-4o-mini", messages=messages, response_format={"type": "json_object"}
                    )
                    
                    result_json = json.loads(response.choices[0].message.content)
                    
                    st.success("生成が完了しました！")

                    for item in result_json["names"]:
                        name, yomi, reason, scores = item["name"], item["yomi"], item["reason"], item["scores"]
                        s_total = scores.get("total", 80)
                        
                        categories = ['響き', '字形', '独創', '可読', '願い']
                        values = [scores.get("hibiki", 50), scores.get("jikei", 50), scores.get("doku", 50), scores.get("kadoku", 50), scores.get("negai", 50)]
                        values += [values[0]]; categories += [categories[0]]; values += [values[0]]; categories += [categories[0]]

                        fig = go.Figure(data=[go.Scatterpolar(r=values, theta=categories, fill='toself', name=name, line_color='#00CC96')])
                        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, height=250, margin=dict(t=20, b=20, l=30, r=30))

                        with st.container(border=True):
                            col_text, col_graph = st.columns([1.2, 1])
                            with col_text:
                                st.metric(label="🏅 総合評価", value=f"{s_total}点")
                                st.caption("名前（コピーできます👇）")
                                st.code(f"{name} ({yomi})", language=None)
                                st.write(f"**理由:** {reason}")
                            with col_graph:
                                st.plotly_chart(fig, use_container_width=True)

                        st.session_state.generated_names.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "対象": target_type, "名前": f"{name} ({yomi})", "総合点": s_total, "理由": reason
                        })

                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")


# --------------------------------------------------
# 【タブ2】新機能：プレミアム評価レポート（noteパスワード式）
# --------------------------------------------------
with tab2:
    st.markdown("### 💎 プレミアム詳細診断レポート")
    st.write("候補の名前を多角的に分析し、客観的なリスクや印象を評価するプロフェッショナル専用モードです。")
    
    note_url = "https://note.com/namersai/n/nd1fda095acbc?sub_rt=share_pb"
    
    with st.container(border=True):
        st.markdown("🔒 **この機能を利用するにはアクセスコードが必要です。**")
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
        
        # 評価用により詳細な入力項目を用意
        eval_target = st.selectbox("命名の対象", ["人間（子供など）", "創作キャラクター", "企業・サービス・屋号（BtoB）", "ペット"])
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
                            model="gpt-4o", # プレミアム機能なので精度の高いモデル(GPT-4o)を推奨
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
                            st.metric(label="🏆 総合スコア", value=f"{score} / 100", delta=f"ランク {rank}", delta_color="normal" if rank in ["S", "A"] else "inverse")
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

# =====================================================================
# タブの外（アプリ全体に共通して表示される部分）
# =====================================================================

if st.session_state.generated_names:
    df_log = pd.DataFrame(st.session_state.generated_names)
    csv = df_log.to_csv(index=False).encode('utf-8-sig')
    st.sidebar.markdown("### 履歴管理")
    st.sidebar.download_button("📥 履歴をCSVで保存", data=csv, file_name=f"naming_log_{datetime.now().strftime('%Y%m%d')}.csv", mime='text/csv')

st.markdown("---")
col_feedback1, col_feedback2 = st.columns([2, 1])
with col_feedback1:
    st.write("💡 アプリの改善にご協力ください！")
with col_feedback2:
    st.link_button("🧸アンケートに答える", "https://docs.google.com/forms/d/e/1FAIpQLScEKP2qdJ49NgbjOrq27T4fDaPIXTqrUO74wdFMxMhtwdylPQ/viewform?usp=header", use_container_width=True)














































