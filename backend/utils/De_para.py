import requests
import unicodedata
import functools
import logging
from rapidfuzz import process, fuzz
import pandas as pd

logger = logging.getLogger(__name__)

def limpar_texto(texto):
    if pd.isna(texto):
        return ""
    texto = str(texto).upper().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("utf-8")
    return " ".join(texto.split())

@functools.lru_cache(maxsize=1)
def _buscar_municipios():
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Falha ao buscar municípios do IBGE: {e}")
        return []

def normalizar_cidades(lista_cidades, score_minimo=80):

    municipios = _buscar_municipios()

    # cria estrutura:
    # chave limpa -> nome oficial
    municipios_dict = {}

    for m in municipios:

        nome_oficial = m["nome"]

        nome_limpo = limpar_texto(nome_oficial)

        municipios_dict[nome_limpo] = nome_oficial

    municipios_limpos = list(municipios_dict.keys())

    # =========================
    # MATCHING
    # =========================
    de_para = {}

    for cidade_original in lista_cidades:

        cidade_limpa = limpar_texto(cidade_original)

        if cidade_limpa == "":
            de_para[cidade_original] = None
            continue

        resultado = process.extractOne(
            cidade_limpa,
            municipios_limpos,
            scorer=fuzz.ratio
        )

        melhor_match_limpo = resultado[0]
        score = resultado[1]

        if score >= score_minimo:

            # retorna nome OFICIAL
            nome_oficial = municipios_dict[melhor_match_limpo]

            de_para[cidade_original] = nome_oficial

        else:
            de_para[cidade_original] = None

    de_para.update({'EMBU':'Embu','Embu das Artes':'Embu','VITORIA DA CO':'Vitória da Conquista'})

    return de_para