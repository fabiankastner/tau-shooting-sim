import pandas as pd


def main():
    results_df = pd.read_csv('results.csv')
    
    
    # 
    results_1 = results_df[(results_df.defender_name=='thunderwolf_cavalry_6') & (results_df.score>=0.5)].sort_values(by=['score'], ascending=False).head(5).copy()



if __name__=="__main__":
    main()
