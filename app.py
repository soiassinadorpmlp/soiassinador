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

# --- CREDENCIAIS DIRETAS DO GOOGLE ---
credenciais_dict = {
  "type": "service_account",
  "project_id": "soi-assinador",
  "private_key_id": "eaaef78044d8efc923f18954f006bb24d0411e58",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDB3GkUge7oI5Qp\ndtggpWhjkDpngZuhlRitG1TSF3yAovrXwyoG0COT17wkSqqc/a9Jygt1Lht+iEV7\n/W7YdHrUr6KpRYTMjP6zmPNrsFg3o5DqhXcDrz02H9aoz0ijxkqEpSRoDo7x7mrc\nyauFRErakdTIld0acmErGLexn8jmEElpALDTkfbX2Cvcv37V7OMhcwNRTg7Xrsbu\nIw+asprtY0dGCqyLusPqg4kcujDRSK3lwJpDAt1Pvj7/vjUQp5ml+2RX40FIABIN\nV+8coXDciTZL8CqkkXCrRIhDGtvF5qIV9wz5+v8bTmY4XAigx3cdLcblHDVHCpJv\nmnZ9Lsj/AgMBAAECggEAYFKWt4TT4u4CqROO0bG+C3JXQqSoYoHFcAWbgIQA7Z2N\nS3WCRT5X3xabOeELotN9rAlC5idRq+4jsDa9Q7mkalcWWErdcBFCYJRHpqNJQeP4\nlj5YYzFIFcN+EgRkUFOvJPc0/qr1JYpT+H4PxjinhLBe7IdiA8j/NL2kUBJXbM+f\nbEZ1zUq+mF7KV3Aeg1idb6Sf3ng9SLGCncgo28OxuGyOb3QnHEu8/ssCQVVl/i4y\nDruaUkIZCLWAZ6YA6gUYDKvQQ3eL7Rx7j9TrxnaVxD4UcDYimN0Aq5WijeYMtBy+\nrTP+RRN3j9sPW1hzDsYw7txpPgrtDpe/tmODODNGOQKBgQDjemKHtp0tG6+p9R1n\nmy+0IbmaKtOPw9fj27qRQnjOVtJZ22TC0fpmtkxrhwbDzy1Z7o7c/jj1JOzvMqE\njQ/CwnHe/mjMoO8lM/5csNCpKj2A9p0zuVE8WRGMVoJRvuQUMq0g9oDv9rnkk70U\numzgXs+EonXZF7K5pF6kqXubvYwKBgQDaKvsRwgwZS1kQPyVTglmd+PBsOzmBe9PX\nk2mMwXU6zNdMZsB/LDP3xLKBGmalYz6F2z2mPC1GuqaZKk90LZYT7cQtbBinOsCi\n6k/Fgt77/GKswQBE3BS1mBBECwgTdMl448NXh4gUUjpe3BoyeVWLYZ2fzzCtW6CU\nTvp9oCTYtQKBgQDN3+imrPZpacI9DnLzXrb4zwD8b0ATwAp21Vlvt/o/vMIZwv7Z\nd1KpfNmDA6xysOF5n/c6OPbxnt60yVystJAMExEd4aCVeh2VzQ2rc/cU8v7A5fF2\na4UDGhVQrsa5Fwuy3/5ic9ZT1zd8kN0ykxJ8GTdxG7l8JW3f/SMEDunwwwKBgQCY\ndibkvw3Dc3N3Nhm4pURJcFlb2XuTcFyXr224rs1k3ResTbZCaTqb8LqqHDAVbiiY\nVKFdlXoyjme0a+wAjYbuwF8zOvJzk0xhzYsXxSBdSoAOqAWvGXnjebQMSQVIy3ms\nYMb3WUCQqvIdroUkNsTAVeRYdOtYisrKOfM1bX+ybQKBgGBmnRA9rSmkCUvIFdOS\na5TLa3gv2FW3WdEAihH4DsAtpFZHrmDzkaTJfU4hJcVBciJ7d79Ch6vNNp6P0U87\nXfnbPDFOK7w4+zvSvNJ3x0Uqwh8YEv+wIR0dai8Y133fL5r+VZ++Nkc85lwZf/Ji\n+YmrHSF3MwAVrNhu5z2S6YFZ\n-----END PRIVATE KEY-----\n",
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
    # AJUSTE CIRÚRGICO: Traduz os \n textuais em quebras de linha reais exigidas pelo arquivo PEM
    dados_sanitizados = credenciais_dict.copy()
    dados_sanitizados["private_key"] = dados_sanitizados["private_key"].replace("\\n", "\n")
    
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

# --- MEMÓRIA DO ARQUIVO ORIGINAL ---
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
            if str(a.get("token")) == str(token_acesso):
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
                    valido = (str(a.get("token")) == str(token_acesso) and a.get("status") == "Pendente")
                else:
                    valido = (str(a.get("nome")).lower() == c_nome.lower() and a.get("status") == "Pendente")
                    
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
