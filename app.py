import hashlib
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(
    page_title="Plataforma de Assinaturas",
    page_icon="🖋️",
    layout="wide"
)

# --- CONFIGURAÇÕES FIXAS DA PLATAFORMA ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://soiassinador.streamlit.app"

# --- MEMÓRIA DO SISTEMA DE SESSÃO (PERSISTENTE) ---
if "banco_dados" not in st.session_state:
    st.session_state.banco_dados = {
        "caminho_original": None,
        "conteudo_original": None,
        "hash_seguranca": None,
        "assinantes": []
    }

# --- LEITURA DO TOKEN DA URL ---
token_acesso = st.query_params.get("token", None)

def obter_tabela_historico():
    if not st.session_state.banco_dados["assinantes"]:
        return []
    dados_tabela = []
    for a in st.session_state.banco_dados["assinantes"]:
        dados_tabela.append({
            "Nome": a["nome"],
            "E-mail": a["email"],
            "Status": a["status"],
            "CPF Utilizado": a["cpf"],
            "Data/Hora": a["data"],
            "Token": a["token"]
        })
    return dados_tabela

# --- MOTOR DE DISPARO DE E-MAIL ---
def enviar_email_individual(meu_email, minha_senha_app, email_destino, nome_assinante, link_personalizado):
    try:
        servidor_smtp = "smtp.gmail.com"
        porta = 465
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = email_destino
        msg['Subject'] = "Assinatura Pendente - Plataforma Digital"
        
        corpo = f"""Olá, {nome_assinante}.

Você foi incluído como assinante de um documento oficial.

⚠️ INSTRUÇÕES:
1. Confira a grafia do seu nome para a assinatura: {nome_assinante}
2. Acesse a plataforma pelo seu link exclusivo:
{link_personalizado}

3. Leia atentamente a minuta na tela.
4. Digite seu NOME COMPLETO e seu CPF para validar.

Não é necessário fazer login para assinar.
"""
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        servidor = smtplib.SMTP_SSL(servidor_smtp, porta)
        servidor.login(meu_email, minha_senha_app)
        servidor.sendmail(meu_email, email_destino, msg.as_string())
        servidor.quit()
        return True
    except:
        return False

# --- PROCESSAR ENTRADA DE LOTE ---
def criador_processa_lote(arquivo_pdf, texto_assinantes, meu_email, minha_senha_app, link_sistema):
    if arquivo_pdf is None:
        return st.error("ERRO: Anexe um arquivo PDF.")
    if not texto_assinantes.strip():
        return st.error("ERRO: Insira pelo menos 1 assinante.")
    if not meu_email or not minha_senha_app:
        return st.error("ERRO: Configure suas credenciais de e-mail.")
    
    st.session_state.banco_dados["caminho_original"] = arquivo_pdf.name
    st.session_state.banco_dados["conteudo_original"] = arquivo_pdf.getvalue()
    st.session_state.banco_dados["assinantes"] = []
    
    hasher = hashlib.sha256()
    hasher.update(st.session_state.banco_dados["conteudo_original"])
    st.session_state.banco_dados["hash_seguranca"] = hasher.hexdigest()

    linhas = texto_assinantes.strip().split("\n")
    emails_enviados = 0
    base_url = link_sistema.split("?")[0]
    
    for linha in linhas:
        if ";" in linha:
            partes = linha.split(";")
            nome_limpo = partes[0].strip()
            email_limpo = partes[1].strip()
            token = secrets.token_hex(4)
            
            st.session_state.banco_dados["assinantes"].append({
                "nome": nome_limpo, 
                "email": email_limpo, 
                "token": token,
                "cpf": "", 
                "status": "Pendente", 
                "data": "-"
            })
            
            link_personalizado = f"{base_url}?token={token}"
            enviar_email_individual(meu_email, minha_senha_app, email_limpo, nome_limpo, link_personalizado)
            emails_enviados += 1

    total_cadastrados = len(st.session_state.banco_dados["assinantes"])
    st.session_state.relatorio_envio = f"Lote processado! {emails_enviados} e-mails enviados."
    st.success("Lote disparado com sucesso!")

# --- MENU LATERAL DE ACESSO RESTRITO ---
with st.sidebar:
    st.subheader("Acesso Restrito")
    modo_admin = st.checkbox("Ativar Modo Criador")
    autenticado = False
    
    if modo_admin:
        senha_admin = st.text_input("Senha do Criador", type="password")
        if senha_admin == "ChaveMestra123":
            st.success("Acesso Liberado!")
            autenticado = True
        elif senha_admin:
            st.error("Senha incorreta.")

# --- SE HOUVER TOKEN NA URL, ENTRA DIRETO COMO ASSINANTE SEM EXIGIR NADA ---
if token_acesso:
    autenticado = False

# --- INTERFACE DE ABAS ---
if autenticado:
    aba1, aba2, aba3 = st.tabs(["Painel do Criador", "Página do Assinante", "Histórico do Lote"])
else:
    aba2, = st.tabs(["Página do Assinante"])

# --- CONTEÚDO: PAINEL DO CRIADOR (ADMIN) ---
if autenticado:
    with aba1:
        col1, col2 = st.columns(2)
        with col1:
            campo_meu_email = st.text_input("Seu Gmail de Envio", value=GMAIL_PADRAO)
            campo_minha_senha = st.text_input("Senha de App (16 letras)", type="password")
            campo_link_sistema = st.text_input("Link do seu Sistema", value=LINK_SISTEMA_PADRAO)
            campo_arquivo = st.file_uploader("Arraste o PDF do Contrato", type=["pdf"])
            campo_lote = st.text_area("Lista de Assinantes (Nome; E-mail)", placeholder="João Silva; joao@email.com", height=150)
            
            if st.button("🚀 Disparar E-mails para o Lote", type="primary"):
                criador_processa_lote(campo_arquivo, campo_lote, campo_meu_email, campo_minha_senha, campo_link_sistema)
                
        with col2:
            st.subheader("Painel de Controle")
            if "relatorio_envio" in st.session_state:
                st.text_area("Relatório de Saída", st.session_state.relatorio_envio, height=250)
            else:
                st.info("Aguardando o envio do primeiro lote...")

# --- CONTEÚDO: PÁGINA DO ASSINANTE ---
with aba2:
    st.title("🖋️ Assinatura Eletrônica de Documentos")
    
    assinante_atual = None
    if token_acesso and st.session_state.banco_dados["assinantes"]:
        for a in st.session_state.banco_dados["assinantes"]:
            if str(a["token"]) == str(token_acesso):
                assinante_atual = a
                break

    st.subheader("1. Minuta do Documento para Leitura")
    if st.session_state.banco_dados["conteudo_original"] is not None:
        st.download_button(
            label="📖 Abrir minuta para leitura",
            data=st.session_state.banco_dados["conteudo_original"],
            file_name="minuta_para_leitura.pdf",
            mime="application/pdf"
        )
        st.info("Analise o documento antes de assinar abaixo.")
    else:
        st.warning("Nenhum documento ativo para assinatura no momento.")

    st.subheader("2. Identificação e Validação")
    col3, col4 = st.columns(2)
    with col3:
        nome_sugerido = assinante_atual["nome"] if assinante_atual else ""
        campo_nome_cliente = st.text_input("Nome Completo", value=nome_sugerido)
        campo_cpf_cliente = st.text_input("Digite seu CPF")
        
        if st.button("✍️ Confirmar Assinatura Digital", type="primary"):
            if not st.session_state.banco_dados["assinantes"]:
                st.error("ERRO: Nenhum lote de documento ativo na memória.")
            elif not campo_nome_cliente or not campo_cpf_cliente:
                st.error("ERRO: Preencha Nome e CPF.")
            else:
                encontrado = False
                for a in st.session_state.banco_dados["assinantes"]:
                    valido = False
                    if token_acesso:
                        valido = (str(a["token"]) == str(token_acesso) and a["status"] == "Pendente")
                    else:
                        valido = (a["nome"].lower() == campo_nome_cliente.lower() and a["status"] == "Pendente")
                        
                    if valido:
                        a["status"] = "Assinado"
                        a["cpf"] = campo_cpf_cliente
                        a["data"] = "24/06/2026 15:50"
                        encontrado = True
                        break
                
                if not encontrado:
                    st.error("ERRO: Identificação inválida ou já assinado.")
                else:
                    st.success("Assinatura registrada com sucesso!")
                    
                    # GERAR FOLHA DE ASSINATURAS
                    pdf_folha = "folha_assinaturas_lote.pdf"
                    c = canvas.Canvas(pdf_folha, pagesize=letter)
                    c.rect(40, 40, 532,
