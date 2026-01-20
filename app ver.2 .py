import re, os, logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

logging.basicConfig(level=logging.INFO)

def get_score(pattern, text, default=50):
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        val = int(m.group(1))
    except Exception:
        return default
    # clamp
    return max(0, min(100, val))

# ===== sections の定義（for文より前に必須）=====

# 1. 初期化
response_content = ""
sections = []

# 2. UI
st.title("🧸 名前生成アプリ")

with st.form("name_form"):
    target_type = st.selectbox(
        "対象",
        ["人名", "キャラクター", "ペンネーム", "会社名"]
    )

    gender = st.radio(
        "性別",
        ["指定なし", "男性", "女性"]
    )

    use_kanji = st.text_input(
        "使いたい漢字（任意）",
        placeholder="例：空、光、優"
    )

    avoid_kanji = st.text_input(
        "避けたい漢字（任意）",
        placeholder="例：死、暗"
    )

    wish = st.text_area(
        "込めたい願い・イメージ",
        placeholder="例：やさしく、芯が強い"
    )

    submitted = st.form_submit_button("生成")
    
    if submitted:
    response_content = generate_names(
        target_type=target_type,
        gender=gender,
        use_kanji=use_kanji,
        avoid_kanji=avoid_kanji,
        wish=wish
    )



# 3. データ加工
if response_content:
    sections = response_content.split("\n\n")


sections = []
if response_content and isinstance(response_content, str):
    sections = response_content.split("\n\n")

# --- 表示ループ（例） ---
for section in sections:
    if "名前：" not in section:
        continue

    # スコア取得（日本語含むので明示的に）
    s_hibiki = get_score(r"響き：\s*([0-9]{1,3})点", section)
    s_jikei  = get_score(r"字形：\s*([0-9]{1,3})点", section)
    s_doku   = get_score(r"独創：\s*([0-9]{1,3})点", section)
    s_kadoku = get_score(r"可読：\s*([0-9]{1,3})点", section)
    s_negai  = get_score(r"願い：\s*([0-9]{1,3})点", section)

    name_match = re.search(r"名前：(.+?)(?:\n|$)", section)
    if not name_match:
        logging.warning("名前がパースできません: %r", section[:80])
        continue
    name = name_match.group(1).strip()

    categories = ['響き', '字形', '独創', '可読', '願い']
    values = [s_hibiki, s_jikei, s_doku, s_kadoku, s_negai]
    # copyして閉ループのために最初の要素を付加
    plot_categories = categories + [categories[0]]
    plot_values = values + [values[0]]

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=plot_values,
                theta=plot_categories,
                fill='toself',
                name=name,
                line=dict(color='#00CC96'),
                hovertemplate="%{theta}: %{r}<extra></extra>"
            )
        ]
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tick0=0, dtick=20)
        ),
        showlegend=False,
        height=320,
        margin=dict(t=30, b=10, l=30, r=30)
    )

    # UI: expander で折りたたむ（大量表示対策）
    with st.expander(f"{name} — 平均 {(sum(values)/len(values)):.1f}"):
        # 見た目のボックスを CSS で作る
        st.markdown(
            '<div style="border:1px solid #eee;padding:12px;border-radius:8px">',
            unsafe_allow_html=True
        )
        cols = st.columns([2, 1])
        with cols[0]:
            # 改行を保ちつつ表示（邪魔な空行を削除）
            st.markdown(f"### {name}")
            st.markdown(section.replace("\n", "  \n"))
        with cols[1]:
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # CSV 書き出し（追記時はヘッダを追加しない）
    try:
        filename = Path(f"names_api_{datetime.now().strftime('%Y%m%d')}.csv")
        df = pd.DataFrame([[
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            target_type, gender, use_kanji, avoid_kanji, wish, response_content
        ]], columns=["timestamp", "対象", "性別", "使いたい漢字", "避けたい漢字", "願い", "生成候補"])

        write_header = not filename.exists()
        df.to_csv(filename, index=False, mode="a", header=write_header, encoding="utf-8-sig")
    except Exception as e:
        logging.exception("CSV書き込みに失敗しました: %s", e)
        st.error("サーバ側でCSV保存に失敗しました。")

# 最後のリンク修正（正しい Googleフォーム URL を入れてください）
st.markdown("---")
st.markdown("### 評価アンケートはこちら")
st.markdown("[👉 Googleフォームで評価する](https://docs.google.com/forms/your_form_id_here)")























































