import streamlit as st

def show_title(text):
    st.markdown(f"## {text}")

def info_box(label, content):
    st.info(f"**{label}**\n\n{content}")

def show_ab_tables(dfA, dfB, titleA="リスト A", titleB="リスト B"):
    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"### {titleA}")
        st.table(dfA)
    with colB:
        st.markdown(f"### {titleB}")
        st.table(dfB)
