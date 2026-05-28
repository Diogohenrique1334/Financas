import pandas as pd
import func_leitor_faturas, mover_arquivos
import os

def consolida_faturas(caminho):

    pdfs = [ x for x in os.listdir(caminho) if '.pdf' in x]

    gastos_consolidados = pd.DataFrame()

    for pdf in pdfs:

        print(pdf)

        temp = func_leitor_faturas(fr"{caminho}/{pdf}")

        gastos_consolidados = pd.concat[temp,gastos_consolidados]

        mover_arquivos(caminho_origem=fr"{caminho}/{pdf}",caminho_destino=fr"{caminho}/bkp/{pdf}")

        print(f"Fatura {pdf} movida para {caminho}/bkp")

    return gastos_consolidados