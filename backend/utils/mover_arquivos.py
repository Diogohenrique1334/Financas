from pathlib import Path
import shutil 

def mover_arquivo(caminho_origem: str, caminho_destino: str):
    """
    Move um arquivo de um caminho para outro.

    Parameters
    ----------
    caminho_origem : str
        Caminho completo do arquivo atual.
    caminho_destino : str
        Caminho completo onde o arquivo deve ser movido (incluindo o novo nome, se quiser).

    Exemplo:
        mover_arquivo("C:/entrada/arquivo.xlsx", "C:/saida/arquivo.xlsx")
    """
    origem = Path(caminho_origem)
    destino = Path(caminho_destino)

    # Garante que a pasta destino exista
    destino.parent.mkdir(parents=True, exist_ok=True)

    shutil.move(str(origem), str(destino))
    print(f"Arquivo movido com sucesso para: {destino}")