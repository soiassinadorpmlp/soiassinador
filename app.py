import hashlib
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from pypdf import PdfReader, PdfWriter

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="Plataforma de Assinaturas",
    page_icon="🖋️",
    layout="wide"
)

# --- CONFIGURAÇÕES FIXAS ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://soiassinador.streamlit.app"

# --- CONEXÃO COM O GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro ao conectar com o Google Sheets. Verifique os Secrets.")

def ler_dados_planilha():
    try:
        df = conn.read(ttl="0d")
        return df.to_dict(orient="records")
    except:
        return []

def salvar_dados_planilha(lista_assinantes):
    try:
        df = pd.DataFrame(lista_assinantes)
        conn.update(data=df)
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")

# --- MEMÓRIA DO ARQUIVO ORIGINAL (SESSÃO CURTA) ---
if "pdf_original_conteudo" not in st.session_state:
    st.session_state.pdf_original_conteudo = None
if "hash_seguranca" not in st.session_state:
    st.session_state.hash_seguranca = None

# --- LEITURA DO TOKEN DA URL ---
token_acesso = st.query_params.get("token", None)

# --- MOTOR DE DISPARO DE E-MAIL ---
def enviar_email_individual(meu_email, minha_senha, destino, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = destino
        msg['Subject'] = "Assinatura Digital Pendente"
        
        corpo = f"""Olá, {nome}.

Você foi incluído para assinar um documento oficial.

Acesse pelo link seguro abaixo:
{link}

Digite seu NOME e CPF para validar. Não precisa de login.
"""
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        servidor = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        servidor.login(meu_email, minha_senha)
        servidor.sendmail(meu_email, destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- PROCESSAR ENTRADA DE LOTE ---
def criador_processa_lote(arquivo, texto, meu_email, minha_senha, link_sistema):
    if arquivo is None or not texto.strip():
        return st.error("Erro: Preencha o arquivo e a lista.")
    
    st.session_state.pdf_original_conteudo = arquivo.getvalue()
    hasher = hashlib.sha256()
    hasher.update(st.session_state.pdf_original_conteudo)
    st.session_state.hash_seguranca = hasher.hexdigest()

    linhas = texto.strip().split("\n")
    base_url = link_sistema.split("?")[0]
    
    novos_assinantes = []
    
    for linha in lines:
        if ";" in linha:
            partes = linha.split(";")
            nome_limpo = partes[0].strip()
            email_limpo = partes[1].strip()
            token = secrets.token_hex(4)
            
            novos_assinantes.append({
                "token": token,
                "nome": nome_limpo,
                "email": email_limpo,
                "cpf": "",
                "status": "Pendente",
                "data": "-",
                "hash_doc": st.session_state.hash_seguranca
            })
            
            link_personalizado = f"{base_url}?token={token}"
            enviar_email_individual(meu_email, minha_senha, email_limpo, nome_limpo, link_personalizado)
            
    salvar_dados_planilha(novos_assinantes)
    st.success("Lote enviado e salvo no Google Sheets com sucesso!")

# --- MENU LATERAL DE ACESSO RESTRITO ---
with st.sidebar:
    st.subheader("Controle")
    modo_admin = st.checkbox("Ativar Modo Criador")
    autenticado = False
    if modo_admin:
        senha = st.text_input("Senha", type="password")
        if senha == "ChaveMestra123":
            st.success("Liberado")
            autenticado = True

if token_acesso:
    autenticado = False

# --- ABAS ---
if autenticado:
    aba1, aba2, aba3 = st.tabs(["Criador", "Assinante", "Histórico"])
else:
    aba2, = st.tabs(["Assinante"])

# --- CONTEÚDO: CRIADOR ---
if autenticado:
    with aba1:
        c1, c2 = st.columns(2)
        with c1:
            m_email = st.text_input("Gmail Envio", value=GMAIL_PADRAO)
            m_senha = st.text_input("Senha App", type="password")
            m_link = st.text_input("Link App", value=LINK_SISTEMA_PADRAO)
            m_arq = st.file_uploader("Contrato PDF", type=["pdf"])
            m_lote = st.text_area("Lista (Nome; Email)")
            if st.button("🚀 Enviar Lote", type="primary"):
                criador_processa_lote(m_arq, m_lote, m_email, m_senha, m_link)
        with c2:
            st.subheader("Planilha Ativa")
            dados_atuais = ler_dados_planilha()
            if dados_atuais:
                st.dataframe(pd.DataFrame(dados_atuais), width="stretch")
            else:
                st.info("Nenhum dado na planilha.")

# --- CONTEÚDO: ASSINANTE ---
with aba2:
    st.title("🖋️ Assinatura Eletrônica de Documentos")
    
    lista_banco = ler_dados_planilha()
    assinante_atual = None
    
    if token_acesso and lista_banco:
        for a in lista_banco:
            if str(a["token"]) == str(token_acesso):
                assinante_atual = a
                break

    st.subheader("1. Identificação do Assinante")
    if assinante_atual:
        st.success(f"Documento localizado para: {assinante_atual['nome']}")
    else:
        if token_acesso:
            st.error("Token inválido ou expirado.")
        else:
            st.warning("Aguardando link de acesso exclusivo enviado por e-mail.")

    nome_sug = assinante_atual["nome"] if assinante_atual else ""
    c_nome = st.text_input("Nome Completo", value=nome_sug)
    c_cpf = st.text_input("CPF")
    
    if st.button("✍️ Confirmar Assinatura", type="primary"):
        if not lista_banco:
            st.error("Erro: Banco de dados vazio.")
        elif not c_nome or not c_cpf:
            st.error("Erro: Preencha todos os campos.")
        else:
            encontrado = False
            for a in lista_banco:
                valido = False
                if token_acesso:
                    valido = (str(a["token"]) == str(token_acesso) and a["status"] == "Pendente")
                else:
                    valido = (a["nome"].lower() == c_nome.lower() and a["status"] == "Pendente")
                    
                if valido:
                    a["status"] = "Assinado"
                    a["cpf"] = c_cpf
                    a["data"] = "24/06/2026"
                    encontrado = True
                    break
            
            if not encontrado:
                st.error("Erro: Assinatura inválida ou lote já concluído.")
            else:
                salvar_dados_planilha(lista_banco)
                st.success("Assinatura confirmada e registrada no Google Sheets!")
                st.balloons()

# --- CONTEÚDO: HISTÓRICO ---
if autenticado:
    with aba3:
        st.subheader("Histórico de Assinaturas (Realtime)")
        dados_finais = ler_dados_planilha()
        if dados_finais:
            st.dataframe(pd.DataFrame(dados_finais), width="stretch")
