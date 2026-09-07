import pandas as pd
import json

# CSVファイルの読み込み（実ファイル名に合わせて変更）
live_master = pd.read_csv('浦島坂田船 現場まとめ - 公演マスタ.csv', encoding='utf-8')
song_master = pd.read_csv('浦島坂田船 現場まとめ - 楽曲マスタ.csv', encoding='utf-8')
pattern_detail = pd.read_csv('浦島坂田船 現場まとめ - セトリパターン詳細.csv', encoding='utf-8')
assign_sheet = pd.read_csv('浦島坂田船 現場まとめ - セトリ割当シート.csv', encoding='utf-8')
block_master = pd.read_csv('浦島坂田船 現場まとめ - ブロックマスタ.csv', encoding='utf-8')

# 1. 各種CSVデータの割り当て
df_live = live_master
df_song = song_master
df_pattern = pattern_detail
df_assign = assign_sheet
df_block = block_master

# 2. 楽曲マスタ・ブロックマスタの辞書化
song_dict = df_song.set_index('楽曲ID')['曲名'].to_dict()

block_dict = {}
for block_id, group in df_block.groupby('ブロックID'):
    block_dict[block_id] = group.sort_values('ブロック内曲順')['楽曲ID'].tolist()

def resolve_code(code, assign_row):
    if pd.isna(code): return None
    code = str(code).strip()
    if code in assign_row and pd.notna(assign_row[code]):
        val = str(assign_row[code]).strip()
        if val in ['M_NAN', 'nan', '']: return None
        return val
    return code

# 3. セトリ内で使用されている楽曲IDの集合（used_song_ids）を作成
used_song_ids = set()

for group in df_block.groupby('ブロックID'):
    for s_id in group[1]['楽曲ID']:
        if pd.notna(s_id):
            used_song_ids.add(str(s_id).strip())

assign_map = df_assign.set_index('公演ID')
live_to_songs = {}

for idx, live in df_live.iterrows():
    live_id = str(live['公演ID'])
    songs_list = []

    if live_id in assign_map.index:
        assign_row = assign_map.loc[live_id]
        if isinstance(assign_row, pd.DataFrame):
            assign_row = assign_row.iloc[0]

        pattern_id = assign_row['パターンID']
        pattern_songs = df_pattern[df_pattern['パターンID'] == pattern_id].sort_values('曲順')['楽曲ID'].tolist()

        song_idx = 1
        for p_code in pattern_songs:
            res1 = resolve_code(p_code, assign_row)
            if not res1: continue

            if res1 in block_dict:
                medley_sub_songs = []
                for b_code in block_dict[res1]:
                    res2 = resolve_code(b_code, assign_row)
                    if res2:
                        used_song_ids.add(res2)
                        medley_sub_songs.append({'id': res2, 'title': song_dict.get(res2, res2)})

                if medley_sub_songs:
                    songs_list.append({
                        'idx': song_idx,
                        'is_medley': True,
                        'title': 'メドレー / コーナー',
                        'medley_songs': medley_sub_songs
                    })
                    song_idx += 1
            else:
                used_song_ids.add(res1)
                songs_list.append({
                    'idx': song_idx,
                    'is_medley': False,
                    'id': res1,
                    'title': song_dict.get(res1, res1)
                })
                song_idx += 1

    live_to_songs[live_id] = songs_list

# 4. ツアーごとに公演データをグループ化
tour_groups = {}
for idx, live in df_live.iterrows():
    live_id = str(live['公演ID'])
    date_str = str(live['日付']) if pd.notna(live['日付']) else ''
    date_num = int(date_str.replace('-', '').replace('/', '')) if date_str and date_str != 'nan' and len(date_str) >= 8 else 0
    venue_str = str(live['都道府県・会場']) if pd.notna(live['都道府県・会場']) else '会場未定'
    tour_str = str(live['ツアー名']) if pd.notna(live['ツアー名']) else '単発・企画公演'
    artist_str = str(live['出演者']) if pd.notna(live['出演者']) else '浦島坂田船'

    live_item = {
        'id': live_id,
        'date': date_str,
        'date_num': date_num,
        'venue': venue_str,
        'tour': tour_str,
        'artist': artist_str,
        'search': f"{date_str} {venue_str} {tour_str} {artist_str}".lower()
    }

    if tour_str not in tour_groups:
        tour_groups[tour_str] = []
    tour_groups[tour_str].append(live_item)

tour_list = []
for tour_name, lives in tour_groups.items():
    lives.sort(key=lambda x: x['date_num'])
    first_date = min(l['date_num'] for l in lives if l['date_num'] > 0) if any(l['date_num'] > 0 for l in lives) else 0
    main_artist = lives[0]['artist'] if lives else '浦島坂田船'

    tour_list.append({
        'tour_name': tour_name,
        'artist': main_artist,
        'first_date': first_date,
        'lives': lives
    })

tour_list.sort(key=lambda x: x['first_date'], reverse=True)

# 5. 楽曲マスタのフィルタリング＆グループ化
artist_song_groups = {}

for idx, song in df_song.iterrows():
    s_id = str(song['楽曲ID']).strip()
    title = str(song['曲名']) if pd.notna(song['曲名']) else ''
    artist = str(song['アーティスト']) if 'アーティスト' in song and pd.notna(song['アーティスト']) else (str(song['区分']) if '区分' in song and pd.notna(song['区分']) else '浦島坂田船')

    is_cover = 'カバー' in artist or ('区分' in song and pd.notna(song['区分']) and 'カバー' in str(song['区分']))
    if is_cover and s_id not in used_song_ids:
        continue

    date_val = ''
    for col in ['投稿日', '投稿日付', 'リリース日', '日付']:
        if col in song and pd.notna(song[col]):
            date_val = str(song[col])
            break

    date_num = int(date_val.replace('-', '').replace('/', '')) if date_val and date_val.replace('-', '').replace('/', '').isdigit() else 0

    item = {
        'id': s_id,
        'title': title,
        'artist': artist,
        'date': date_val,
        'date_num': date_num,
        'search': f"{title} {artist}".lower()
    }

    if artist not in artist_song_groups:
        artist_song_groups[artist] = []
    artist_song_groups[artist].append(item)

artist_song_list = []
for artist_name, songs in artist_song_groups.items():
    artist_song_list.append({
        'artist_name': artist_name,
        'songs': songs
    })

def artist_sort_key(x):
    aname = x['artist_name']
    if '浦島坂田船' in aname: return 0
    if aname in ['うらたぬき', '志麻', 'あほの坂田。', 'となりの坂田。', 'センラ']:
        order_map = {'うらたぬき': 1, '志麻': 2, 'あほの坂田。': 3, 'となりの坂田。': 3, 'センラ': 4}
        return order_map.get(aname, 5)
    return 0.5

artist_song_list.sort(key=artist_sort_key)

# HTML出力（以下、既存のテンプレート処理）