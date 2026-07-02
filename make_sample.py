"""
Writes sample_players.csv: real players, APPROXIMATE recent per-game stats.
For accurate live numbers run fetch_data.py instead. Stats here are
illustrative so the dashboard runs out of the box without a network call.
Columns: PLAYER,TEAM,POS,AGE,GP,MIN,PTS,TRB,AST,STL,BLK,TOV,TS_PCT
"""
import pandas as pd

rows = [
    # PG
    ("Shai Gilgeous-Alexander","OKC","PG",26,76,34.2,32.7,5.0,6.4,1.7,1.0,2.4,0.637),
    ("Luka Doncic","LAL","PG",25,50,35.4,28.2,8.2,7.7,1.8,0.5,3.6,0.580),
    ("Trae Young","ATL","PG",26,76,36.0,24.2,3.1,11.6,1.2,0.2,4.7,0.560),
    ("Ja Morant","MEM","PG",25,50,30.3,23.2,4.1,7.3,1.2,0.4,3.2,0.550),
    ("Tyrese Haliburton","IND","PG",24,73,33.6,18.6,3.5,9.2,1.4,0.7,1.6,0.600),
    ("Stephen Curry","GSW","PG",36,70,32.2,24.5,4.4,6.0,1.1,0.4,3.1,0.630),
    ("Jalen Brunson","NYK","PG",28,65,35.4,26.0,3.0,7.3,0.9,0.2,2.4,0.580),
    ("Cade Cunningham","DET","PG",23,70,35.0,26.1,6.1,9.1,1.0,0.8,4.4,0.560),
    # SG
    ("Anthony Edwards","MIN","SG",23,79,36.3,27.6,5.7,4.5,1.2,0.6,3.2,0.580),
    ("Devin Booker","PHX","SG",28,75,37.2,25.6,4.1,7.1,0.9,0.3,3.1,0.580),
    ("Donovan Mitchell","CLE","SG",28,71,31.4,24.0,4.5,5.0,1.3,0.5,2.6,0.580),
    ("Jaylen Brown","BOS","SG",28,63,34.3,22.2,5.8,4.5,1.2,0.4,2.6,0.550),
    ("Tyrese Maxey","PHI","SG",24,52,37.7,26.3,3.3,6.1,1.8,0.4,2.4,0.560),
    ("Desmond Bane","MEM","SG",26,69,32.0,19.2,6.1,5.3,1.2,0.5,2.4,0.590),
    # SF
    ("Jayson Tatum","BOS","SF",27,72,36.4,26.8,8.7,6.0,1.1,0.5,2.9,0.590),
    ("LeBron James","LAL","SF",40,70,34.9,24.4,7.8,8.2,1.0,0.6,3.7,0.600),
    ("Kevin Durant","PHX","SF",36,62,36.5,26.6,6.0,4.2,0.8,1.2,3.0,0.630),
    ("Kawhi Leonard","LAC","SF",33,37,32.3,21.5,5.9,3.1,1.6,0.5,1.6,0.600),
    ("Jalen Williams","OKC","SF",23,71,32.4,21.6,5.3,5.1,1.6,0.7,2.3,0.580),
    ("Franz Wagner","ORL","SF",23,60,33.5,24.0,5.7,4.7,1.3,0.6,2.7,0.550),
    ("Paul George","PHI","SF",34,41,32.6,16.2,5.3,4.3,1.8,0.4,2.3,0.550),
    ("DeMar DeRozan","SAC","SF",35,77,35.9,22.2,3.9,4.4,0.9,0.3,1.6,0.560),
    # PF
    ("Giannis Antetokounmpo","MIL","PF",30,67,34.2,30.4,11.9,6.5,0.9,1.2,3.1,0.600),
    ("Anthony Davis","DAL","PF",31,51,34.3,24.7,11.6,3.5,1.2,2.1,2.1,0.570),
    ("Evan Mobley","CLE","PF",23,71,30.6,18.5,9.3,3.2,0.9,1.6,1.8,0.620),
    ("Paolo Banchero","ORL","PF",22,46,34.1,25.9,7.5,4.8,0.9,0.6,3.0,0.550),
    ("Pascal Siakam","IND","PF",30,78,32.7,20.2,7.0,3.4,0.9,0.5,1.9,0.600),
    ("Julius Randle","MIN","PF",30,69,32.5,18.7,7.1,4.7,0.7,0.3,2.6,0.560),
    ("Scottie Barnes","TOR","PF",23,65,32.8,19.3,7.7,5.8,1.3,0.9,2.6,0.550),
    # C
    ("Nikola Jokic","DEN","C",29,70,36.7,29.6,12.7,10.2,1.8,0.6,3.3,0.660),
    ("Joel Embiid","PHI","C",30,19,30.2,23.8,8.2,4.5,0.7,0.9,3.6,0.580),
    ("Victor Wembanyama","SAS","C",21,46,33.2,24.3,11.0,3.7,1.1,3.8,3.2,0.590),
    ("Karl-Anthony Towns","NYK","C",29,72,35.0,24.4,12.8,3.1,1.0,0.7,2.9,0.630),
    ("Bam Adebayo","MIA","C",27,78,34.3,18.1,9.6,4.3,1.3,0.8,2.2,0.550),
    ("Rudy Gobert","MIN","C",32,72,33.9,12.0,10.9,1.6,0.7,1.5,1.4,0.660),
    ("Alperen Sengun","HOU","C",22,76,31.5,19.1,10.3,4.9,1.1,0.8,2.5,0.580),
    ("Domantas Sabonis","SAC","C",28,70,34.7,19.1,13.9,6.0,0.8,0.5,3.2,0.610),
    ("Jarrett Allen","CLE","C",26,82,31.0,13.5,9.7,2.7,0.9,1.1,1.4,0.700),
]

cols = ["PLAYER","TEAM","POS","AGE","GP","MIN",
        "PTS","TRB","AST","STL","BLK","TOV","TS_PCT"]
pd.DataFrame(rows, columns=cols).to_csv("sample_players.csv", index=False)
print(f"Wrote sample_players.csv ({len(rows)} players)")
