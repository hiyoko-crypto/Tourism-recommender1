import streamlit as st

def show_title(text):
    st.markdown(f"## {text}")

def info_box(label, content):
    st.info(f"**{label}**\n\n{content}")
