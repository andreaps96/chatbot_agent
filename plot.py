import openai
import pandas as pd
import matplotlib.pyplot as plt
import os
from dotenv import load_dotenv
import re


load_dotenv()
api_key = os.getenv('openai_key')

def completa_prompt(prompt):
    """
    Invoca il modello OpenAI per completare il prompt.
    """
    
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # Usa il modello GPT-4 o GPT-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0,  # Facoltativo: controlla la creatività della risposta
        )
        return response.choices[0].message.content
    except Exception as e:
        print(e)

def descrivi_dataframe(df):
   
    """
    Fornisce una descrizione generale del DataFrame per aiutare l'agente a scegliere un grafico.
    """
    descrizione = f"""
    Ecco alcune informazioni sul DataFrame:
    - Colonne e tipi di dati: {df.dtypes.to_dict()}
    - Statistiche numeriche: {df.describe().to_dict()}
    - Dimensioni df: {df.shape}
    - Colonne del df: {list(df.columns)}
    - Valori nulli: {df.isnull().sum().to_dict()}
    - Valori univoci per colonna: {df.nunique().to_dict()}
    """
    return descrizione

def genera_grafico_con_agente(df):
    """
    Utilizza un agente (GPT-4) per scegliere il tipo di grafico e generarlo.
    """
    # Controlla se l'input è un DataFrame Pandas
    if not isinstance(df, pd.DataFrame):
        try:
            # Se l'input è una stringa, tenta di caricarlo come CSV o JSON
            if isinstance(df, str):
                if df.strip().startswith("{") or df.strip().startswith("["):
                    # Prova a leggere come JSON
                    df = pd.read_json(df)
                else:
                    # Prova a leggere come CSV
                    from io import StringIO
                    df = pd.read_csv(StringIO(df))
            else:
                # Prova a creare un DataFrame direttamente
                df = pd.DataFrame(df)
            print("Input trasformato con successo in un DataFrame Pandas.")
        except Exception as e:
            raise ValueError(f"Errore nella conversione dell'input in DataFrame Pandas: {e}")
    #print(df)
    # Descrivi il DataFrame
    descrizione_df = descrivi_dataframe(df)
    #print(descrizione_df)

    # Prompt per il modello
    prompt = f"""
        Ecco una descrizione del DataFrame:
        {descrizione_df}

        Scegli il tipo di grafico più adatto per visualizzare i dati contenuti nel dataframe {df} e genera il codice Python necessario.
        Usa matplotlib o seaborn.

        Adatta la dimensione della finestra di visualizzazione alla mole di dati che devi visualizzare. Puoi modificare anche i bins, sfrutta il metodo plot.figure(figsize)
        Decidi il tipo di grafico da usare, per esempio grafico a barre, grafico a dispersione, grafico a torta, ecc. Scegli in base alla tipologia di dati contenuti nel dataframe, al numero di colonne e al tipo dei dati per migliorare la visualizzazione.
        Usa una griglia. (plot.grid())

        Inerisci nel grafico tutti i dati presenti nel dataframe. Se usi una varibialie temporale come valore dell'asse x, sfrutta tutti i dati contenuti nel {df}. Puoi evitare dei dati solo se ci sono campi con valori NaN
        Aggiungi una legenda e sii accurato nel definirla. Quando usi la legenda, sfrutta i nomi delle colonne del dataframe.

        Assicurati che il codice sia autonomamente eseguibile e valido nel contesto, non commettere errori di sintassi. Scrivi il codice più semplice e pulito possibile.
    """

    # Richiedi il codice al modello
    codice_generato = completa_prompt(prompt)

    #print(codice_generato)
    # Estrai il codice tra i backtick
    
    codice_pulito = re.findall(r'```python\n(.*?)```', codice_generato, re.DOTALL)
    
    if codice_pulito:
        try:
            # Esegui il codice estratto
            exec(codice_pulito[0], {'df': df, 'pd': pd, 'plt': plt})
            plt.show()
        except Exception as e:
            print(f"Errore durante l'esecuzione del codice generato: {str(e)}")
    else:
        print("Nessun codice valido trovato.")



