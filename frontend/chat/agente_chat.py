"""Componente de chat do Agente de Gastos (camada de apresentação).

Renderiza a conversa, envia a pergunta ao backend via ``api.client`` e — o
diferencial anti-alucinação — exibe as **fontes** de cada resposta: quais
ferramentas o agente chamou e os números que elas devolveram. Isso prova ao
usuário (e ao recrutador) que o valor é real, não inventado pelo modelo.

Mantém o histórico simples na sessão (``st.session_state``). Toda a lógica de
agregação/LLM fica no backend; aqui só orquestramos UI + chamada HTTP.
"""

import httpx
import streamlit as st

from api.client import perguntar_agente

_CHAVE_HISTORICO = "chat_agente_historico"

_SUGESTOES = [
    "Qual é a minha média de gasto mensal?",
    "Quanto gastei com transporte em março de 2025?",
    "Quanto ainda devo de parcelas em aberto?",
    "Eu gastei mais em abril ou em março de 2025?",
]


def _formatar_parametros(parametros: dict) -> str:
    """Formata os parâmetros de uma chamada de ferramenta para exibição."""
    if not parametros:
        return "sem parâmetros"
    return ", ".join(f"{chave}={valor!r}" for chave, valor in parametros.items())


def _exibir_fontes(resposta: dict) -> None:
    """Mostra ferramentas, dados usados e metadados de custo/latência."""
    ferramentas = resposta.get("ferramentas_usadas", [])
    with st.expander(f"🔍 Fontes ({len(ferramentas)} ferramenta(s) consultada(s))"):
        if not ferramentas:
            st.caption("Nenhuma ferramenta foi chamada — resposta sem dado de origem.")
        for ferramenta, fonte in zip(ferramentas, resposta.get("dados_brutos", [])):
            st.markdown(
                f"**`{ferramenta['ferramenta']}`** · {_formatar_parametros(ferramenta['parametros'])}"
            )
            resultado = fonte.get("resultado", {})
            recorte = resultado.get("recorte") if isinstance(resultado, dict) else None
            if recorte:
                st.dataframe(recorte, use_container_width=True, hide_index=True)
            else:
                st.json(resultado, expanded=False)

        tokens = resposta.get("tokens", {})
        st.caption(
            f"⏱️ {resposta.get('latencia_ms', 0)} ms · "
            f"🪙 {tokens.get('total_tokens', 0)} tokens "
            f"({tokens.get('input_tokens', 0)} entrada / {tokens.get('output_tokens', 0)} saída)"
        )


def _processar_pergunta(pergunta: str) -> None:
    """Chama o agente, trata erros e adiciona a troca ao histórico."""
    st.session_state[_CHAVE_HISTORICO].append({"role": "user", "conteudo": pergunta})
    try:
        with st.spinner("Consultando seus gastos…"):
            resposta = perguntar_agente(pergunta)
        st.session_state[_CHAVE_HISTORICO].append(
            {"role": "assistant", "conteudo": resposta["resposta"], "fontes": resposta}
        )
    except httpx.HTTPError as exc:
        st.session_state[_CHAVE_HISTORICO].append(
            {"role": "assistant", "conteudo": f"⚠️ Não consegui responder agora: {exc}", "fontes": None}
        )


def render() -> None:
    """Renderiza a página de chat do Agente de Gastos."""
    st.set_page_config(layout="wide", page_title="Agente de Gastos")
    st.title("💬 Agente de Gastos")
    st.caption(
        "Pergunte em linguagem natural sobre seus gastos. As respostas vêm de "
        "consultas determinísticas aos seus dados — clique em **Fontes** para conferir."
    )

    if _CHAVE_HISTORICO not in st.session_state:
        st.session_state[_CHAVE_HISTORICO] = []

    if not st.session_state[_CHAVE_HISTORICO]:
        st.markdown("**Experimente:**")
        for coluna, sugestao in zip(st.columns(len(_SUGESTOES)), _SUGESTOES):
            if coluna.button(sugestao, use_container_width=True):
                _processar_pergunta(sugestao)
                st.rerun()

    for mensagem in st.session_state[_CHAVE_HISTORICO]:
        with st.chat_message(mensagem["role"]):
            st.markdown(mensagem["conteudo"])
            if mensagem.get("fontes"):
                _exibir_fontes(mensagem["fontes"])

    if pergunta := st.chat_input("Pergunte sobre seus gastos…"):
        _processar_pergunta(pergunta)
        st.rerun()
