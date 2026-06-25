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

# --- CONEXÃO COM GOOGLE SHEETS VIA SECRETS ---
def obter_cliente_sheets():
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    creds_dict = dict(st.secrets["gcredentials"])
    
    if "private_key" in creds_dict:
        raw_key = creds_dict["private_key"]
        # Limpa cabeçalhos, rodapés, quebras de linha e espaços para obter apenas os dados puros
        raw_key = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
        raw_key = raw_key.replace("\n", "").replace("\r", "").replace(" ", "").strip()
        
        # Reconstrói o bloco PEM garantindo exatamente 64 caracteres por linha (padrão RFC)
        linhas_pem = [raw_key[i:i+64] for i in range(0, len(raw_key), 64)]
        bloco_pem_correto = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(linhas_pem) + "\n-----END PRIVATE KEY-----\n"
        creds_dict["private_key"] = bloco_pem_correto
        
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
    
    for linha in linhas:
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
