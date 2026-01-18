import streamlit as st
import json
import uuid, random, csv, os
from datetime import datetime
import pandas as pd
from utils.ui_helpers import show_ab_tables, show_aspect_eval, overall_eval_ui, show_ab_tables_aspect
from utils.load_data import load_all, load_viewpoint_descriptions, load_spot_urls
from utils.scoring import compute_user_preference, recommend_spots
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# =====================
# 条件割り当て（4C2 = 6通り）
# =====================
CONDITIONS = [
    ("noaspect_all", "aspect_all"),
    ("noaspect_all", "aspect_top5"),
    ("noaspect_all", "aspect_exclude_interest_top5"),
    ("aspect_all", "aspect_top5"),
    ("aspect_all", "aspect_exclude_interest_top5"),
    ("aspect_top5", "aspect_exclude_interest_top5")
]


def get_condition_from_log():
    # Google Sheets 認証
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)

    sheet = client.open_by_key(
        st.secrets["gcp_service_account"]["sheet_id"]
    ).sheet1

    values = sheet.get_all_values()

    # ログが無い場合
    if len(values) <= 1:
        return random.choice(CONDITIONS)

    header = values[0]
    data_rows = values[1:]

    try:
        cond_idx = header.index("condition_pair")
    except ValueError:
        return random.choice(CONDITIONS)

    # カウント用辞書（キーは "A|B" 形式）
    counts = {"|".join(c): 0 for c in CONDITIONS}

    for row in data_rows:
        if len(row) <= cond_idx:
            continue
        cond = row[cond_idx]
        if cond in counts:
            counts[cond] += 1

    # 全部 0 の場合
    if all(v == 0 for v in counts.values()):
        return random.choice(CONDITIONS)

    # 最小値の条件を選ぶ
    min_count = min(counts.values())
    candidates = [c for c, v in counts.items() if v == min_count]

    # "A|B" → ("A","B") に戻す
    chosen = random.choice(candidates)
    condA, condB = chosen.split("|")

    return (condA, condB)

# =====================
# 初期化
# =====================
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "step" not in st.session_state:
    st.session_state.step = 0

if "mode" not in st.session_state: 
    st.session_state.mode = None


# =====================
# ログ保存
# =====================
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def save_log(data):
    # Google Sheets 認証
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)

    sheet = client.open_by_key(
        st.secrets["gcp_service_account"]["sheet_id"]
    ).sheet1

    # 既存データを取得
    existing = sheet.get_all_values()

    # ============================
    # ★ ログがまだ無い場合（1行目が空）
    # ============================
    if len(existing) == 0:
        header = list(data.keys())  # ← data のキーをそのままヘッダーにする
        sheet.append_row(header)

    else:
        # 既存ヘッダーを取得
        header = existing[0]

        # ★ data に新しいキーが追加されていたらヘッダーに追加する
        new_keys = [k for k in data.keys() if k not in header]
        if new_keys:
            header += new_keys
            sheet.update('1:1', [header])  # 1行目を更新

    # ============================
    # ★ ヘッダー順にデータを並べる
    # ============================
    row = [data.get(col, "") for col in header]

    sheet.append_row(row)


# =====================
# メイン処理
# =====================
def main():
    st.title("観光地推薦システム")

    spot_url_dict = load_spot_urls()

    # =====================
    # Step 0: 説明・同意
    # =====================
    if st.session_state.step == 0:
        st.markdown("""
        ### 実験へのご協力のお願い
        本実験は観光地推薦に関する研究目的で実施されます。
        回答は匿名で収集され、個人が特定されることはありません。
        所要時間は約5〜7分です。

        ページをロードすると最初からになってしまうので、ロードしなおさないでください。
        """)

        st.session_state.mode = st.radio( 
            "実験モードを選んでください", 
            [ "何も指示がない場合はこちらを選択", "管理者用" ] 
        )

        # ---------------------------- 
        # 管理者用の場合：名前選択 
        # ---------------------------- 
        if st.session_state.mode == "管理者用":
            admin_name = st.selectbox( 
                "ユーザーを選択してください", ["花道さん", "太郎さん", "花子さん"] 
            ) 
            # 管理者用データをロード（あなたの保存済みデータをここで読み込む） 
            admin_data = { 
                "花道さん": { 
                    "name": "花道さん", 
                    "age_group": "20代", 
                    "condition_pair": ("noaspect_all", "aspect_top5"), 
                    "selected_viewpoints": ["テーマ公園・テーマ施設"], 
                    "visited_spots": ["東京スカイツリー", "東京ソラマチ", "明治神宮", "ユニバーサル・スタジオ・ジャパン（USJ）", "原爆ドーム"], 
                    "spot_feedback": {"東京スカイツリー": {"viewpoints": ["テーマ公園・テーマ施設"]}, "東京ソラマチ": {"viewpoints": ["テーマ公園・テーマ施設"]}, "明治神宮": {"viewpoints": ["神社・寺院・教会"]}, "ユニバーサル・スタジオ・ジャパン（USJ）": {"viewpoints": ["テーマ公園・テーマ施設"]}, "原爆ドーム": {"viewpoints": ["史跡"]}} 
                }, 
                "太郎さん": { 
                    "name": "太郎さん", 
                    "age_group": "30代", 
                    "condition_pair": ("aspect_all", "aspect_top5"), 
                    "selected_viewpoints": ["滝", "海岸・岬", "岩石・洞窟", "集落・街", "庭園・公園", "建造物", "テーマ公園・テーマ施設", "温泉", "食" ],
                    "visited_spots": ["城崎温泉の町並み", "城崎温泉", "嚴島神社", "出雲大社", "おもちゃ王国"], 
                    "spot_feedback": {"城崎温泉の町並み": {"viewpoints": ["食"]}, "城崎温泉": {"viewpoints": ["温泉"]}, "嚴島神社": {"viewpoints": ["神社・寺院・教会"]}, "出雲大社": {"viewpoints": ["食"]}, "おもちゃ王国": {"viewpoints": ["テーマ公園・テーマ施設"]}} 
                }, 
                "花子さん": { 
                    "name": "花子さん", 
                    "age_group": "20代", 
                    "condition_pair": ("noaspect_all", "aspect_all"), 
                    "selected_viewpoints": ["テーマ公園・テーマ施設"], 
                    "visited_spots": ["東京スカイツリー", "お台場", "ユニバーサル・スタジオ・ジャパン（USJ）", "錦帯橋", "しまなみ海道"], 
                    "spot_feedback": {"東京スカイツリー": {"viewpoints": ["建造物"]}, "お台場": {"viewpoints": ["テーマ公園・テーマ施設"]}, "ユニバーサル・スタジオ・ジャパン（USJ）": {"viewpoints": ["テーマ公園・テーマ施設"]}, "錦帯橋": {"viewpoints": ["建造物"]}, "しまなみ海道": {"viewpoints": ["建造物"]}}
                } 
            }
            selected_user = admin_data[admin_name]

            if st.button("このユーザーで開始"): 
                # Step1 をスキップして Step2 へ 
                st.session_state.name = selected_user["name"]
                st.session_state.age_group = selected_user["age_group"]
                st.session_state.selected_viewpoints = selected_user["selected_viewpoints"] 
                st.session_state.visited_spots = selected_user["visited_spots"] 
                st.session_state.spot_feedback = selected_user["spot_feedback"] 
                
                # condition_pair もセット 
                st.session_state.condition_pair = selected_user["condition_pair"] 
                st.session_state.step = 2 
                st.rerun() 
            st.stop()
        
        st.subheader("参加者情報の入力")
        name = st.text_input("お名前（ニックネーム可）を入力してください")
        age_group = st.selectbox( "年代を選択してください", ["10代", "20代", "30代", "40代", "50代", "60代以上"] )
        if st.checkbox("内容を理解し、同意します"):
            if st.button("実験を開始する"):
                st.session_state.name = name
                st.session_state.age_group = age_group
                st.session_state.condition_pair = get_condition_from_log()
                st.session_state.step = 1
                st.rerun()
        return

    viewpoint_list, spot_lists, spot_scores = load_all()
    viewpoint_descriptions = load_viewpoint_descriptions()

    # =====================
    # Step 1: 興味のある観点 + 行った観光地
    # =====================
    if st.session_state.step == 1:

        st.subheader("あなたが旅行先を選ぶときに「ここが大事だな」と思うポイントを教えてください。（1つ以上）")
        st.caption("（例：自然が好き、歴史が好き、食べ歩きが好き など）")
        st.caption("意味が分からない観点だけ、必要に応じて説明を確認してください。")

        selected_viewpoints = []

        for i in range(0, len(viewpoint_list), 3):

            if i == 0:
                st.markdown("### 自然資源")
        
            # i=9 のときだけ特別処理
            if i == 9:
                cols = st.columns(3)
                vp = viewpoint_list[i]
        
                with cols[0]:
                    with st.expander(vp):   # ← ここを expander にする
                        checked = st.checkbox(vp, key=f"vp_{vp}")
                        if checked:
                            selected_viewpoints.append(vp)
        
                        desc = viewpoint_descriptions.get(vp, f"{vp} の説明文は準備中です")
                        lines = desc.splitlines()
                        for line in lines[:3]:
                            st.caption(line)
        
                        if len(lines) > 3:
                            with st.expander("続きを見る"):
                                for line in lines[3:]:
                                    st.write(line)
        
                    st.markdown("### 人文資源")
        
                continue
        
            # 通常処理（3列表示）
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(viewpoint_list):
                    vp = viewpoint_list[i + j]
                    with col:
                        with st.expander(vp):   # ← ここを expander にする
                            checked = st.checkbox(vp, key=f"vp_{vp}")
                            if checked:
                                selected_viewpoints.append(vp)
        
                            desc = viewpoint_descriptions.get(vp, f"{vp} の説明文は準備中です")
                            lines = desc.splitlines()
        
                            for line in lines[:3]:
                                st.caption(line)
        
                            if len(lines) > 3:
                                with st.expander("続きを見る"):
                                    for line in lines[3:]:
                                        st.write(line)


                                    
        st.subheader("行って良かった観光地を5つ選んでください")
        st.caption("東京・関西・中国地方のどの地域から選んでも構いません。")
        st.caption("全部を見る必要はありません。目についたものから直感で選んで大丈夫です。")
        
        visited_spots = []
        spot_feedback = {}
        
        # 1ページあたりの件数
        PAGE_SIZE = 10
        
        for region, spots in spot_lists.items():
            with st.expander(region):
        
                # ページ数を計算
                total = len(spots)
                pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        
                # ページ番号をセッションに保存
                page_key = f"page_{region}"
                if page_key not in st.session_state:
                    st.session_state[page_key] = 0
        
                page = st.session_state[page_key]
        
                # 今表示する範囲
                start = page * PAGE_SIZE
                end = min(start + PAGE_SIZE, total)
                current_spots = spots[start:end]
        
                # 横2列レイアウト
                cols = st.columns(2)
        
                for idx, spot in enumerate(current_spots):
                    col = cols[idx % 2]
        
                    with col:
                        checked = st.checkbox(spot, key=f"spot_{region}_{spot}")
                        if checked:
                            visited_spots.append(spot)
        
                            viewpoints = st.multiselect(
                                f"{spot} で良かった観点（1つ以上選択してください）",
                                viewpoint_list,
                                key=f"viewpoints_{spot}"
                            )
        
                            spot_feedback[spot] = {"viewpoints": viewpoints}
        
                # まだ次のページがある場合だけ「続きを見る」ボタンを表示
                if end < total:
                    if st.button("続きを見る", key=f"next_{region}"):
                        st.session_state[page_key] += 1
                        st.experimental_rerun()

                
        # 右上に選択数を表示
        col_left, col_right = st.columns([1, 1])
        with col_right:
            st.markdown(
                f"<div style='text-align: right; font-size: 18px; font-weight: bold;'>"
                f"現在の選択数：{len(visited_spots)} 件"
                f"</div>",
                unsafe_allow_html=True
            )

        if st.button("次へ"):
            if len(selected_viewpoints) == 0: 
                st.error("興味のある観点を少なくとも 1 つ選んでください。") 
                st.stop()

            if len(visited_spots) != 5:
                st.error(f"観光地をちょうど 5 つ選択してください。（現在: {len(visited_spots)} 件）") 
                st.stop() 

            for spot in visited_spots: 
                if len(spot_feedback[spot]["viewpoints"]) == 0: 
                    st.error(f"{spot} の良かった観点を少なくとも1つ選んでください。") 
                    st.stop()

            st.session_state.selected_viewpoints = selected_viewpoints
            st.session_state.visited_spots = visited_spots
            st.session_state.spot_feedback = spot_feedback

            st.session_state.step = 2
            st.rerun()
        return

    # =====================
    # Step 2: A/B 推薦比較 + 全観光地評価
    # =====================
    if st.session_state.step == 2:
        st.subheader("おすすめ観光地の比較")
        st.markdown("### これから 2つのおすすめリスト（A と B） を表示します。どちらが あなたの好みに合っているか を直感的に選んでください。")
    
        # --- 条件ペアを取り出す ---
        condA, condB = st.session_state.condition_pair
    
        # --- A のユーザ嗜好を計算 ---
        user_pref_A = compute_user_preference(
            st.session_state.visited_spots,
            st.session_state.spot_feedback,
            spot_scores,
            st.session_state.selected_viewpoints,
            condition=condA
        )
    
        # --- B のユーザ嗜好を計算 ---
        user_pref_B = compute_user_preference(
            st.session_state.visited_spots,
            st.session_state.spot_feedback,
            spot_scores,
            st.session_state.selected_viewpoints,
            condition=condB
        )
    
        # --- A の推薦 ---
        recA, excludedA = recommend_spots(
            user_pref_df=user_pref_A,
            spot_scores=spot_scores,
            condition=condA,
            selected_viewpoints=st.session_state.selected_viewpoints,
            visited_spots=st.session_state.visited_spots
        )
    
        # --- B の推薦 ---
        recB, excludedB = recommend_spots(
            user_pref_df=user_pref_B,
            spot_scores=spot_scores,
            condition=condB,
            selected_viewpoints=st.session_state.selected_viewpoints,
            visited_spots=st.session_state.visited_spots
        )
    
        # 保存（ログ用）
        st.session_state.user_pref_A = user_pref_A
        st.session_state.user_pref_B = user_pref_B
        st.session_state.recA = recA
        st.session_state.recB = recB
        st.session_state.excludedA = excludedA
        st.session_state.excludedB = excludedB
    
        # --- 表示用に整形 ---
        dfA = recA.copy()
        dfA = dfA.drop(columns=["スコア"], errors="ignore")
        dfA.index = range(1, len(dfA) + 1)
        if "スコア" in dfA.columns:
            dfA["スコア"] = dfA["スコア"].round(3)
    
        dfB = recB.copy()
        dfB = dfB.drop(columns=["スコア"], errors="ignore")
        dfB.index = range(1, len(dfB) + 1)
        if "スコア" in dfB.columns:
            dfB["スコア"] = dfB["スコア"].round(3)
    
        # --- A/B を横並びで表示 ---
        show_ab_tables(dfA, dfB)
    
        st.markdown("---")
    
        # ============================
        # ここから全観光地の評価（重複は除く）
        # ============================
    
        st.subheader("以下の観光地に行ったことがありますか？")
        st.caption("観光地名をクリックすると、その場所の特徴や口コミページが見られます。気になる観光地は、お調べいただいても構いません。")
    
        # --- A と B のスポットを統合（重複除去） ---
        spots_A = list(dfA["スポット"])
        spots_B = list(dfB["スポット"])
        all_spots = list(dict.fromkeys(spots_A + spots_B))  # 重複除去＋順序保持
    
        # --- 観点ごとに min-max 正規化 ---
        df_norm = spot_scores.copy()
        viewpoint_cols = [c for c in df_norm.columns if c != "スポット"]
    
        for col in viewpoint_cols:
            col_values = df_norm[col].astype(float)
            min_v = col_values.min()
            max_v = col_values.max()
            if max_v == min_v:
                df_norm[col] = 0.5
            else:
                df_norm[col] = (col_values - min_v) / (max_v - min_v)
    
        # --- 評価用辞書 ---
        if "spot_questions" not in st.session_state:
            st.session_state.spot_questions = {}
    
        # --- 各観光地を評価 ---
        for idx, spot in enumerate(all_spots, start=1):
    
            # 観点スコア表示
            with st.expander(f"{idx}. {spot}"):
                st.write("#### 観点スコア")
    
                detail = (
                    df_norm[df_norm["スポット"] == spot]
                    .drop(columns=["スポット"])
                    .T
                )
                detail.columns = ["スコア"]
                detail["スコア"] = detail["スコア"].round(3)
                detail = detail.sort_values("スコア", ascending=False).head(5)
    
                st.table(detail)
    
                # 口コミURL
                if spot in spot_url_dict:
                    st.markdown(f"**口コミURL：** [こちらをクリック]({spot_url_dict[spot]})")
                else:
                    st.caption("口コミURLは登録されていません")
    
            visited = st.radio(
                f"{spot} について当てはまるものを選んでください",
                ["行ったことがある", "名前や内容は知っている", "知らなかった"],
                key=f"visited_{spot}"
            )    
    
            st.session_state.spot_questions[spot] = {
                "visited": visited
            }
    
        st.markdown("---")

        # ============================ 
        # A の全体評価 
        # ============================ 
        sat_A, favor_A = overall_eval_ui("A", dfA)
        # ============================ 
        # B の全体評価 
        # ============================ 
        sat_B, favor_B = overall_eval_ui("B", dfB)
        # ============================
        # A/B 比較
        # ============================
        # --- A/B を横並びで表示 ---
        show_ab_tables(dfA, dfB)
        
        st.subheader("どちらの推薦リストが良いと思いましたか？")
    
        ab_choice = st.radio(
            "選択してください",
            [
                "1: A がよい",
                "2: どちらかというとA がよい ",
                "3: どちらとも言えない",
                "4: どちらかというとB がよい",
                "5: B がよい"
            ]
        )

        ab_why = st.text_area(
            "そのように感じた理由を教えてください。もしあれば、決め手になった観光地名も書いていただけると助かります。",
            height=150,
        )
    
        if st.button("次へ"):
            st.session_state.sat_A = sat_A
            st.session_state.favor_A = favor_A
        
            st.session_state.sat_B = sat_B
            st.session_state.favor_B = favor_B
        
            st.session_state.ab_choice = ab_choice
            st.session_state.ab_why = ab_why

            st.session_state.dfA = dfA
            st.session_state.dfB = dfB
        
            st.session_state.step = 3
            st.rerun()
        return

    # =====================
    # Step 3: 観点スコア（種明かし） + アンケート
    # =====================
    if st.session_state.step == 3:
    
        st.subheader("あなたの好みの「傾向」の推定結果")
        st.write("ここでは、A と B のおすすめ結果から推定した “あなたの好み” をまとめて表示します。これが最後のページです。")

        st.markdown("---")
        st.markdown("## A と B の “好みの傾向” の比較")

        prefA = st.session_state.user_pref_A
        prefB = st.session_state.user_pref_B

        prefA["元々興味あり"] = prefA["興味あり"].apply(lambda x: "〇" if x != 0 else "")
        prefB["元々興味あり"] = prefB["興味あり"].apply(lambda x: "〇" if x != 0 else "")
        prefA["あなたの好み"] = prefA["観点"]
        prefB["あなたの好み"] = prefB["観点"]
        prefA["スコア"] = prefA["総合スコア"]
        prefB["スコア"] = prefB["総合スコア"]
        prefA = prefA[["あなたの好み", "スコア", "元々興味あり"]]
        prefB = prefB[["あなたの好み", "スコア", "元々興味あり"]]
        show_ab_tables_aspect(prefA, prefB)

        match_compare = st.radio(
            "A と B のどちらの内容が実際の「あなたの好み」に近いと思いましたか？", 
            ["A の方が近い", "どちらかというと A", "どちらとも言えない", "どちらかというと B", "B の方が近い"], 
            horizontal=True,
        )     
        match_why = st.text_area(
            "上のように判断した理由を教えてください。どの「あなたの好み」をみて判断しましたか？", 
            height=150 
        )
        accept_compare = st.radio(
            "どちらの方が “意外な好み” が多いと感じましたか？", 
            ["A の方が多い", "どちらかというと A", "どちらとも言えない", "どちらかというと B", "B の方が多い"], 
            horizontal=True,
        )

        aspect_comment_compare = st.text_area(
            "そのように判断した理由を教えてください。どの「あなたの好み」をみて判断しましたか？",
            height=150 
        )        


        if st.button("送信して終了"):
            save_log({
                "user_id": st.session_state.user_id,
                "name": st.session_state.name,
                "age_group": st.session_state.age_group,
                "condition_pair": f"{st.session_state.condition_pair[0]}|{st.session_state.condition_pair[1]}",
                
                "selected_viewpoints": ",".join(st.session_state.selected_viewpoints),
                "visited_spots": ",".join(st.session_state.visited_spots),
                "spot_feedback": json.dumps(st.session_state.spot_feedback, ensure_ascii=False),

                "recA": json.dumps(st.session_state.recA.to_dict(orient="records"), ensure_ascii=False), 
                "recB": json.dumps(st.session_state.recB.to_dict(orient="records"), ensure_ascii=False), 
                "excludedA": json.dumps(st.session_state.excludedA, ensure_ascii=False), 
                "excludedB": json.dumps(st.session_state.excludedB, ensure_ascii=False), 
                
                "user_pref_A": json.dumps(st.session_state.user_pref_A.to_dict(orient="records"), ensure_ascii=False), 
                "user_pref_B": json.dumps(st.session_state.user_pref_B.to_dict(orient="records"), ensure_ascii=False),

                # --- A の全体評価 --- 
                "sat_A": st.session_state.sat_A, 
                "favor_A": st.session_state.favor_A, 
                
                # --- B の全体評価 --- 
                "sat_B": st.session_state.sat_B, 
                "favor_B": st.session_state.favor_B,
                
                "spot_questions": json.dumps(st.session_state.spot_questions, ensure_ascii=False),

                "ab_choice": st.session_state.ab_choice, 
                "ab_why": st.session_state.ab_why,

                "match_compare": match_compare,
                "match_why": match_why,
                "accept_compare": accept_compare,
                "aspect_comment_compare": aspect_comment_compare,

                "timestamp": datetime.now().isoformat()
            })

            st.success("ご協力ありがとうございました！")
            st.session_state.step = 4
            st.rerun()
        return

    # =====================
    # Step 4: 完了画面
    # =====================
    if st.session_state.step == 4:
        st.success("実験は以上です。ご協力ありがとうございました！")
        return


if __name__ == "__main__":
    main()
