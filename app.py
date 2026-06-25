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
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import base64
import json
import io

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="Plataforma de Assinaturas",
    page_icon="🖋️",
    layout="wide"
)

# --- CONFIGURAÇÕES FIXAS ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://engenhariapmlp.streamlit.app"
SPREADSHEET_ID = "13Vyiy-XBzR969JPTMJlWK3gpKcLRi9ftVRcO3kinoWE"
PASTA_DRIVE_ID = "1fDD1nh2CrgveEg5NiIPeUjnK4RyWHiot"

# --- CONEXÃO SEGURA VIA BASE64 (SHEETS E DRIVE) ---
def obter_credenciais():
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    b64_data = st.secrets["GOOGLE_CREDS_BASE64"]
    json_string = base64.b64decode(b64_data).decode('utf-8')
    creds_dict = json.loads(json_string)
    return Credentials.from_service_account_info(creds_dict, scopes=escopos)

def obter_cliente_sheets():
    try:
        creds = obter_credenciais()
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro crítico nas credenciais do Sheets: {e}")
        return None

def obter_servico_drive():
    try:
        creds = obter_credenciais()
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Erro crítico nas credenciais do Drive: {e}")
        return None

# --- FUNÇÕES DE FAZER UPLOAD DE MINUTA PRO DRIVE ---
def upload_pdf_para_drive(nome_arquivo, conteudo_bytes):
    try:
        service = obter_servico_drive()
        if not service:
            return None
        
        metadata = {
            'name': nome_arquivo,
            'parents': [PASTA_DRIVE_ID]
        }
        
        fh = io.BytesIO(conteudo_bytes)
        media = MediaIoBaseUpload(fh, mimetype='application/pdf', resumable=True)
        
        arquivo_criado = service.files().create(
            body=metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # Garante permissão de leitura para qualquer um com o link ver o PDF
        service.permissions().create(
            fileId=arquivo_criado.get('id'),
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        return arquivo_criado.get('webViewLink')
    except Exception as e:
        st.error(f"Erro ao enviar PDF para o Google Drive: {e}")
        return None

# --- INTERAÇÃO COM PLANILHA ---
def ler_dados_planilha():
    try:
        gc = obter_cliente_sheets()
        if gc is None:
            return []
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Erro ao acessar a planilha de assinaturas: {e}")
        return []

def salvar_dados_planilha(lista_assinantes):
    try:
        gc = obter_cliente_sheets()
        if gc is None:
            return
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        worksheet.clear()
        df = pd.DataFrame(lista_assinantes)
        set_with_dataframe(worksheet, df)
    except Exception as e:
        st.error(f"Erro ao salvar dados no sistema: {e}")

# --- MOTOR DE DISPARO DE E-MAIL ---
def enviar_email_individual(meu_email, minha_senha, destino, nome, link):
    try:
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = destino
        msg['Subject'] = "Assinatura Digital Pendente"
        
        corpo = f"Olá, {nome}.\n\nVocê foi incluído para assinar um documento oficial da engenharia.\n\nAcesse pelo link seguro abaixo para ler a minuta e assinar:\n{link}\n\nDigite seu NOME e CPF para validar. Não precisa de login."
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        servidor = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        servidor.login(meu_email, minha_senha)
        servidor.sendmail(meu_email, destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- CONTROLE DE ESTADO (SESSION STATE) ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

token_acesso = st.query_params.get("token", None)

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

# --- LER BANCO DE DADOS EM TEMPO REAL ---
lista_banco = ler_dados_planilha()

# --- CONTEÚDO: CRIADOR ---
if st.session_state.autenticado:
    with aba1:
        c1, c2 = st.columns(2)
        with c1:
            m_email = st.text_input("Gmail Envio", value=GMAIL_PADRAO)
            m_senha = st.text_input("Senha App", type="password")
            m_link = st.text_input("Link App", value=LINK_SISTEMA_PADRAO)
            m_arq = st.file_uploader("Contrato PDF (Minuta)", type=["pdf"])
            m_lote = st.text_area("Lista (Nome; Email)")
            
            if st.button("🚀 Enviar Lote", type="primary"):
                if m_arq is not None and m_lote.strip() and m_senha:
                    pdf_conteudo = m_arq.getvalue()
                    
                    # Faz o upload da minuta para o Google Drive e pega o link público
                    st.info("Fazendo upload seguro da minuta para o Google Drive...")
                    link_drive_pdf = upload_pdf_para_drive(m_arq.name, pdf_conteudo)
                    
                    if not link_drive_pdf:
                        st.error("Falha ao salvar o arquivo no Drive. Verifique as permissões da pasta.")
                    else:
                        hasher = hashlib.sha256()
                        hasher.update(pdf_conteudo)
                        hash_seguranca = hasher.hexdigest()
                        
                        linhas = m_lote.strip().split("\n")
                        base_url = m_link.split("?")[0]
                        novos_assinantes = []
                        
                        progresso = st.progress(0)
                        total = len(linhas)
                        
                        for idx, inline in enumerate(linhas):
                            if ";" in inline:
                                partes = inline.split(";")
                                nome_limpo = partes[0].strip()
                                email_limpo = partes[1].strip()
                                token = secrets.token_hex(4)
                                
                                novos_assinantes.append({
                                    "token": token,
                                    "nome": nome_limpo,
                                    "email": email_limpo,
                                    "cpf": "",
                                    "status
