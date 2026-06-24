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
SPREADSHEET_ID = "13Vyiy-XBzR969JPTMJlWK3gpKcLRi9ftVRcO3kinoWE"

# --- CHAVE PRIVADA ENVIADA POR VOCÊ (LINHA ÚNICA DEFINITIVA) ---
CHAVE_PROPRIA_NOVA = r"-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCpPvjTTPOpXt7E\nH8ANQjWbiDWHWz8VjHhIxCrMAYxIc3Ge9fmBNqC99UM4NMCPamzFtu2FfU87zx5F\nbaCpVYBmSxzclTf7r+7Zmkd5qPJYK3BHylajH7lVGqSaXply78xtKV7KMcDFgKUV\nsmWf/5AsJGprvVb9nY6Kq2OKHa3wi2+isX7EzLNG2NpeWS9k/tG6cI3uQ91EFTRd\n9URkENfySweM3gfGPduJfZuI0eK5UQ5oHDlZzPA/4QOEj/lkLrFJlpNZ1B7Vn93B\nnod0lrf5n4bgrpliz/+kOEhk7PLhv8EvbNB662GV0i1aK31oN4cUoBI8yMvHLhF9\njRRhmNEnAgMBAAECggEAM/hy1wvHvMg1lrr7MfcVWBO9ADoMRpUycIHQdIG7LppI\nlxwISF3agUpZoF5OjRuMmDACgt3GYWLJ9F7kGWt4eLDzBWdK4B4XtblS3nB7Loj0\nOw9OiFvbAN+kEQUgkLNDLngoM+WQQPWue9mirD2Ba5SpGzlyh4GEvl8/uy8+9OCU\nYVaTY8llP++WfecEldqvwTOB3cPcNo8qC+7bAVwHbp2yiz2HfBqw6dQz0NuzHPK7\n+am+h0ZNirxEn2ZBo3GaN3u2XPYTQ4P2NPBbxRjfniGHjNa5m0BdO2R/NpTWX/vW\nT3Qp9mZ5p1PfY2MJEQsXtbwN6qxNsgRfBLcprhWiZQKBgQDa38FYdxHQjbYLeRZQ\nF36rh4dyxK771uwo7zoULemBZenclYfPP3otCyiWzs1AwQW2sMgcfRv1dEn9q+S3\lsAzwT3d0GPCZs6FYvRtBtUFBwcDUBpOT4v2gWdg7cQJGcWyzYEINy+W7WbQs3Qd\nR+uCUoqeHJwEIfPFepSfK/lqqwKBgQDF9DMyuIymwMiCqoxVytkXfRn0Arq0yKMj\nPqKTB8rPPdiR2LXkJCaAxk4T0bD7InJYew33vhSxsDK1U+3HsV3OEsZ6nkN/jcvi\nmGwoFci2OSMcehq9f9AV76zqZymqDvtOMVjQPV4aJxsKOtNhhkIzhaTT9h37Gnff\nHs7HiREzdQKBgQDKi9Z473dk8D9PTrb/Vz65raoC41CrbbEOEJRGqFY2kQFiSF5t\nw+hkVrcxGB+JlRacgewtsPl2pC70uWXnH3Kucl22L2qiNFFZzsEzQ+dNx7sNrcsq\nPSLg88+fO2j2owr49IQ7/hXkLb2/1NHXZv7ik1AEEaWvjVvxnAZ9ZkxiEQKBgFKh\nrmGE0gmlvc11neEOLPL2IMhP/1oJyreipMCVZx59ZZL0EHFseboVjXAOfz9F0M+I\nhnsdGIxXzcMNhttt+YdVJQ74U5rCORKcp8FP3pnaXgK8Ib9qxBT0GI08hRLc8CBi\nzv0WMNrf6hSqG6TBI49YQUbNnRQ9pz43IQAAAnMlAoGBAMtS16j3H35cOeGULuh9oMfUFIUPpBveuMP6rVohAz9KpOwChVU4EG+0/ILs1mGYivZLrIczBpFgkquME4OT/NoEymjC8pn/KSmCsbT7aLr3d2yolF3WN6sdbymjN5GVDoqwkyycWhDCcwrd97pVXdXaeg1dyoshfJ8vVT+OlX+z\n-----END PRIVATE KEY-----\n"

credenciais_dict = {
    "type": "service_account",
    "project_id": "soi-assinador",
    "private_key_id": "eaaef78044d8efc923f18954f006bb24d0411e58",
    "private_key": "",
    "client_email": "assinador-sheets@soi-assinador.iam.gserviceaccount.com",
    "client_id": "104754261635399610959",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/raw/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/assinador-sheets%40soi-assinador.iam.gserviceaccount.com"
}

# --- CONEXÃO DIRETA COM GOOGLE SHEETS ---
def obter_cliente_sheets():
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    dados_sanitizados = credenciais_dict.copy()
    
    raw_key = CHAVE_PROPRIA_NOVA
    raw_key = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
    raw_key = raw_key.replace("\\n", "").replace("\n", "").replace(" ", "").strip()
    
    linhas_pem = [raw_key[i:i+64] for i in range(0, len(raw_key), 64)]
    bloco_pem_correto = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(linhas_pem) + "\n-----END PRIVATE KEY-----\n"
    
    dados_sanitizados["private_key"] = bloco_pem_correto
    creds = Credentials.from_service_account_info(dados_sanitizados, scopes=escopos)
    return gspread.authorize(creds)

def ler_dados_planilha():
    try:
        gc = obter_cliente_sheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
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
        st.error(f"Erro ao salvar na planilha: {e}")

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
    modo_admin = st.checkbox("Ativar Modo Criador", value=st.session_state.autenticado)
    
    if modo_admin:
        senha = st.text_input("
