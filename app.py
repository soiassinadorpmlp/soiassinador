import hashlib
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
import pandas as pd
from gspread_dataframe import set_with_dataframe
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="Plataforma de Assinaturas",
    page_icon="🖋️",
    layout="wide"
)

# --- CONFIGURAÇÕES FIXAS ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://soiassinador.streamlit.app"
SPREADSHEET_ID = "13Vyiy-XBzR969JPTMJlWK3gpKcLRi9ftVRcO3kinoWE"

# --- CONEXÃO COM GOOGLE SHEETS VIA SECRETS MULTILINHA ---
def obter_cliente_sheets():
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # Monta as credenciais pegando o texto puro salvo no painel
    creds_dict = {
        "type": st.secrets["google_type"],
        "project_id": st.secrets["google_project_id"],
        "private_key_id": st.secrets["google_private_key_id"],
        "private_key": st.secrets["google_private_key"],
        "client_email": st.secrets["google_client_email"],
        "client_id": st.secrets["google_client_id"],
        "auth_uri": st.secrets["google_auth_uri"],
        "token_uri": st.secrets["google_token_uri"],
        "auth_provider_x509_cert_url": st.secrets["google_auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["google_client_x509_cert_url"]
    }
        
    creds = Credentials.from_service_account_info(creds_dict, scopes=escopos)
    return gspread.authorize(creds)

def ler_dados_planilha():
    try:
        gc = obter_cliente_sheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Erro ao acessar a planilha de assinaturas: {e}")
        return []

def salvar_dados_planilha(lista_assinantes):
    try:
        gc = obter_cliente_sheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        worksheet.clear()
        df = pd.DataFrame(lista_assinantes)
        set_with_dataframe(worksheet, df)
    except Exception as e:
        st.error(f"Erro ao salvar dados no sistema: {e}")

# --- CONTROLE DE ESTADO (SESSION STATE) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "pdf_original_conteudo" not in st.session_state:
    st.session_state.pdf_original_conteudo = None
if "hash_seguranca" not in st.session_state:
    st.session_state.hash_seguranca = None

token_acesso = st.query_params.get("token", None)

# --- MOTOR DE DISPARO DE E-MAIL ---
def enviar_email_individual(meu_email, minha_senha, destino, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = destino
        msg['Subject'] = "Assinatura Digital Pendente"
        
        corpo = f"Olá, {nome}.\n\nVocê foi incluído para assinar um documento oficial.\n\nAcesse pelo link seguro abaixo:\n{link}\n\nDigite seu NOME e CPF para validar. Não precisa de login."
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        servidor = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        servidor.login(meu_email, minha_senha)
        servidor.sendmail(meu_email, destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- MENU LATERAL DE ACESSO RESTRITO ---
with st.sidebar:
    st.subheader("Controle")
    modo_admin = st.checkbox("Ativar Modo Criador", value=st.session_state.autenticado)
    
    if modo_admin:
        senha = st.text_input("Senha", type="password")
        if st.button("🔓 Entrar"):
            if senha == "ChaveMestra123":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    else:
        st.session_state.autenticado = False

if token_acesso:
    st.session_state.autenticado = False

# --- DEFINE VISIBILIDADE DAS ABAS ---
if st.session_state.autenticado:
    aba1, aba2, aba3 = st.tabs(["Criador", "Assinante", "Histórico"])
else:
    aba2, = st.tabs(["Assinante"])

# --- CONTEÚDO: CRIADOR ---
if st.session_state.autenticado:
    with aba1:
        c1, c2 = st.columns(2)
        with c1:
            m_email = st.text_input("Gmail Envio", value=GMAIL_PADRAO)
            m_senha = st.text_input("Senha App", type="password")
            m_link = st.text_input("Link App", value=LINK_SISTEMA_PADRAO)
            m_arq = st.file_uploader("Contrato PDF", type=["pdf"])
            m_lote = st.text_area("Lista (Nome; Email)")
            if st.button("🚀 Enviar Lote", type="primary"):
                if m_arq is not None and m_lote.strip():
                    st.session_state.pdf_original_conteudo = m_arq.getvalue()
                    hasher = hashlib.sha256()
                    hasher.update(st.session_state.pdf_original_conteudo)
                    st.session_state.hash_seguranca = hasher.hexdigest()
                    linhas = m_lote.strip().split("\n")
