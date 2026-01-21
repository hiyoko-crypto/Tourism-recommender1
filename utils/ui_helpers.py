import streamlit as st

def show_title(text):
    st.markdown(f"## {text}")

def info_box(label, content):
    st.info(f"**{label}**\n\n{content}")

def show_ab_tables(dfA, dfB, titleA="観光地リスト A", titleB="観光地リスト B"):
    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"### {titleA}")
        st.table(dfA)
    with colB:
        st.markdown(f"### {titleB}")
        st.table(dfB)

def overall_eval_ui(label, dfA):
    st.subheader(f"観光地リスト {label} の全体評価") 
    st.markdown("---")
    st.table(dfA)
    sat = st.slider(f"{label} の観光地推薦リストにどのくらい満足しましたか？", 1, 5, 3)
    favor = st.slider(f"{label} の観光地推薦リストは、あなたの好みに合っていましたか？", 1, 5, 3)
    st.markdown("---")
    return sat, favor

def show_ab_tables_aspect(dfA, dfB, titleA="好みリスト A", titleB="好みリスト B"):
    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"### {titleA}")
        st.table(dfA)
    with colB:
        st.markdown(f"### {titleB}")
        st.table(dfB)

def show_aspect_eval(label, user_pref_df, selected_viewpoints):
    st.markdown(f"## {label} の観点スコア")

    df = user_pref_df.copy()
    df["スコア"] = df["総合スコア"].round(3)
    df["元々興味あり"] = df["観点"].apply(
        lambda v: "◯" if v in selected_viewpoints else ""
    )
    df["あなたの好み"] = df["観点"]
    st.table(df[["あなたの好み", "スコア", "元々興味あり"]])

    match = st.slider(f"{label} はあなた自身の認識と一致していると感じましたか？", 1, 5, 3)
    accept = st.slider(f"{label} で表示された観点の中に、意外だと感じたものはありましたか？", 1, 5, 3)
    friendly = st.slider(f"{label} に関してなぜこれらの観光地が推薦されたのか、理解しやすかったですか？", 1, 5, 3)
    comment = st.text_area(f"{label} に関してよかった点悪かった点があればご記入ください", height=120)

    return match, accept, friendly, comment
