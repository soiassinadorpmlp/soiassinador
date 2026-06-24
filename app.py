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
st.set_page_config(page_title="Plataforma de Assinaturas", page_icon="🖋️", layout="wide")

# --- CONFIGURAÇÕES FIXAS DA PLATAFORMA ---
GMAIL_PADRAO = "soiassinadorpmlp@gmail.com"
LINK_SISTEMA_PADRAO = "https://soiassinador.streamlit.app"

# --- MEMÓRIA DO SISTEMA DE SESSÃO ---
if "banco_dados" not in st.session_state:
    st.session_state.banco_dados = {
        "caminho_original": None,
        "conteudo_original": None,
        "hash_seguranca": None,
        "assinantes": []
    }

if "modo_administrador" not in st.session_state:
    st.session_state.modo_administrador = False

# --- LEITURA DO TOKEN EXCLUSIVO DA URL (NÃO EXIGE LOGIN) ---
url_params = st.query_params
token_acesso = url_params.get("token", None)

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

# --- MOTOR DE DISPARO REAL ---
def enviar_email_individual(meu_email, minha_senha_app, email_destino, nome_assinante, link_personalizado):
    try:
        servidor_smtp = "smtp.gmail.com"
        porta = 465
        msg = MIMEMultipart()
        msg['From'] = meu_email
        msg['To'] = email_destino
        msg['Subject'] = "Assinatura Pendente - Plataforma Digital"
        
        corpo = f"""Olá, {nome_assinante}.

Você foi incluído como assinante de um documento oficial em nossa plataforma.

⚠️ INSTRUÇÕES IMPORTANTES PARA A ASSINATURA:
1. Confira a grafia do seu nome para a assinatura: {nome_assinante}
2. Acesse a plataforma pelo seu link exclusivo de acesso seguro:
{link_personalizado}

3. Leia atentamente a minuta do documento disponível na tela.
4. Digite obrigatoriamente o seu NOME COMPLETO (exatamente com a grafia acima) e o seu CPF para validar o documento.

Não é necessário criar conta ou fazer login para assinar.
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
    if not link_sistema.strip():
        return st.error("ERRO: Insira o link do seu sistema.")

    st.session_state.banco_dados["caminho_original"] = arquivo_pdf.name
    st.session_state.banco_dados["conteudo_original"] = arquivo_pdf.getvalue()
    st.session_state.banco_dados["assinantes"] = []
    
    hasher = hashlib.sha256()
    hasher.update(st.session_state.banco_dados["conteudo_original"])
    st.session_state.banco_dados["hash_seguranca"] = hasher.hexdigest()

    linhas = texto_assinantes.strip().split("\n")
    emails_enviados = 0
    linhas_ignoradas = 0
    
    base_url = link_sistema.split("?")[0]
    
    for linha in linhas:
        if ";" in linha:
            partes = linha.split(";")
            nome_limpo = partes[0].strip()
            email_limpo = partes[1].strip()
            token = secrets.token_hex(4)
            
            st.session_state.banco_dados["assinantes"].append({
                "nome": nome_limpo, "email": email_limpo, "token": token,
                "cpf": "", "status": "Pendente", "data": "-"
            })
            
            link_personalizado = f"{base_url}?token={token}"
            
            sucesso = enviar_email_individual(meu_email, minha_senha_app, email_limpo, nome_limpo, link_personalizado)
            if sucesso:
                emails_enviados += 1
        else:
            linhas_ignoradas += 1

    total_cadastrados = len(st.session_state.banco_dados["assinantes"])
    relatorio = f"""=== LOTE PROCESSADO ===
1. Hash SHA-256: {st.session_state.banco_dados['hash_seguranca']}
2. Disparos: {emails_enviados} e-mails enviados com sucesso.
3. Linhas ignoradas: {linhas_ignoradas}
4. Total na memória: {total_cadastrados} assinantes cadastrados."""
    
    st.session_state.relatorio_envio = relatorio
    st.success("Lote disparado com sucesso!")

# --- MENU LATERAL DE ACESSO RESTRITO ---
with st.sidebar:
    st.subheader("Acesso Restrito")
    if not st.session_state.modo_administrador:
        senha_admin = st.text_input("Senha do Criador", type="password")
        if st.button("Liberar Painel"):
            if senha_admin == "ChaveMestra123":
                st.session_state.modo_administrador = True
                st.query_params.clear()
                st.rerun()
            else:
                st.error("Senha incorreta.")
    else:
        st.success("Modo Criador Ativo")
        if st.button("Sair do Painel (Modo Assinante)"):
            st.session_state.modo_administrador = False
            st.rerun()

# --- DEFINIÇÃO DAS ABAS DISPONÍVEIS CONFORME PERMISSÃO ---
if st.session_state.modo_administrador:
    aba1, aba2, aba3 = st.tabs(["Painel do Criador", "Página do Assinante", "Histórico do Lote"])
else:
    aba2, = st.tabs(["Página do Assinante"])

# --- CONTEÚDO: PAINEL DO CRIADOR (ADMIN) ---
if st.session_state.modo_administrador:
    with aba1:
        col1, col2 = st.columns(2)
        with col1:
            campo_meu_email = st.text_input("Seu Gmail de Envio", value=GMAIL_PADRAO)
            campo_minha_senha = st.text_input("Sua Senha de App do Gmail (16 letras)", type="password", placeholder="Digite as 16 letras aqui")
            campo_link_sistema = st.text_input("Link do seu Sistema", value=LINK_SISTEMA_PADRAO)
            campo_arquivo = st.file_uploader("Arraste o PDF do Contrato", type=["pdf"])
            campo_lote = st.text_area("Lista de Assinantes (Nome; E-mail)", placeholder="João Silva; joao@email.com", height=150)
            
            if st.button("🚀 Disparar E-mails para o Lote", type="primary"):
                criador_processa_lote(campo_arquivo, campo_lote, campo_meu_email, campo_minha_senha, campo_link_sistema)
                st.rerun()
                
        with col2:
            st.subheader("Painel de Controle")
            if "relatorio_envio" in st.session_state:
                st.text_area("Relatório de Saída", st.session_state.relatorio_envio, height=250)
            else:
                st.info("Aguardando o envio do primeiro lote...")

# --- CONTEÚDO: PÁGINA DO ASSINANTE (PÚBLICA / FILTRADA POR TOKEN) ---
with aba2:
    st.title("🖋️ Assinatura Eletrônica de Documentos")
    
    assinante_atual = None
    if token_acesso and st.session_state.banco_dados["assinantes"]:
        for a in st.session_state.banco_dados["assinantes"]:
            if a["token"] == token_acesso:
                assinante_atual = a
                break

    st.subheader("1. Minuta do Documento para Leitura")
    if st.session_state.banco_dados["conteudo_original"] is not None:
        st.download_button(
            label="📖 Abrir minuta em nova aba / Baixar para leitura",
            data=st.session_state.banco_dados["conteudo_original"],
            file_name="minuta_para_leitura.pdf",
            mime="application/pdf"
        )
        st.info("Utilize o botão acima para analisar integralmente o teor do documento antes de preencher a assinatura abaixo.")
    else:
        st.warning("Nenhum documento ativo para assinatura no momento. Aguarde o envio do link oficial pelo organizador.")

    st.subheader("2. Identificação e Validação")
    col3, col4 = st.columns(2)
    with col3:
        nome_sugerido = list()
        if assinante_atual:
            nome_sugerido = assinante_atual["nome"]
        else:
            nome_sugerido = ""
            
        campo_nome_cliente = st.text_input("Nome Completo do Assinante", value=nome_sugerido, placeholder="Exatamente como recebido no e-mail")
        campo_cpf_cliente = st.text_input("Digite seu CPF")
        
        if st.button("✍️ Confirmar Assinatura Digital", type="primary"):
            if not st.session_state.banco_dados["assinantes"]:
                st.error("ERRO: Nenhum lote de documento ativo.")
            elif not campo_nome_cliente or not campo_cpf_cliente:
                st.error("ERRO: Preencha Nome e CPF.")
            else:
                encontrado = False
                for a in st.session_state.banco_dados["assinantes"]:
                    valido = False
                    if token_acesso:
                        valido = (a["token"] == token_acesso and a["status"] == "Pendente")
                    else:
                        valido = (a["nome"].lower() == campo_nome_cliente.lower() and a["status"] == "Pendente")
                        
                    if valido:
                        a["status"] = "Assinado"
                        a["cpf"] = campo_cpf_cliente
                        a["data"] = "24/06/2026 14:35"
                        encontrado = True
                        break
                
                if not encontrado:
                    st.error("ERRO: Identificação inválida, não cadastrada ou documento já assinado.")
                else:
                    st.success(f"Obrigado, {campo_nome_cliente}! Assinatura registrada com sucesso.")
                    
                    # GERAR FOLHA DE ASSINATURAS
                    pdf_folha = "folha_assinaturas_lote.pdf"
                    c = canvas.Canvas(pdf_folha, pagesize=letter)
                    c.setLineWidth(1)
                    c.setStrokeColorRGB(0.7, 0.7, 0.7)
                    c.rect(40, 40, 532, 712)
                    c.setFont("Helvetica-Bold", 16)
                    c.setFillColorRGB(0.1, 0.2, 0.4)
                    c.drawString(60, 710, "PROTOCOLO DE ASSINATURAS DIGITAIS")
                    c.setFont("Helvetica", 10)
                    c.setFillColorRGB(0.3, 0.3, 0.3)
                    c.drawString(60, 690, "Identificador Único (Hash SHA-256) do Original:")
                    c.setFont("Helvetica-Oblique", 9)
                    c.drawString(60, 675, f"{st.session_state.banco_dados['hash_seguranca']}")
                    c.setLineWidth(0.5)
                    c.line(60, 660, 552, 660)
                    
                    y = 620
                    for a in st.session_state.banco_dados["assinantes"]:
                        if y < 80:
                            c.showPage()
                            y = 710
                        c.setFillColorRGB(0.96, 0.96, 0.98)
                        c.rect(60, y - 45, 492, 55, fill=1, stroke=0)
                        c.setFillColorRGB(0, 0, 0)
                        c.setFont("Helvetica-Bold", 11)
                        c.drawString(70, y, f"Assinante: {a['nome']}")
                        c.setFont("Helvetica", 9)
                        c.setFillColorRGB(0.2, 0.2, 0.2)
                        c.drawString(70, y - 18, f"E-mail: {a['email']}")
                        
                        if a["status"] == "Assinado":
                            c.setFillColorRGB(0.1, 0.5, 0.2)
                            status_texto = f"STATUS: ASSINADO | CPF: {a['cpf']} | Data: {a['data']}"
                        else:
                            c.setFillColorRGB(0.7, 0.1, 0.1)
                            status_texto = "STATUS: PENDENTE"
                        c.setFont("Helvetica-Bold", 9)
                        c.drawString(70, y - 34, status_texto)
                        y -= 70
                    c.save()

                    # COMPILAR ARQUIVO FINAL
                    pdf_final_caminho = "documento_lote_finalizado.pdf"
                    escritor = PdfWriter()
                    
                    with open("temp_orig.pdf", "wb") as f_temp:
                        f_temp.write(st.session_state.banco_dados["conteudo_original"])
                        
                    for pagina in PdfReader("temp_orig.pdf").pages:
                        escritor.add_page(pagina)
                    for pagina in PdfReader(pdf_folha).pages:
                        escritor.add_page(pagina)
                        
                    escritor.encrypt(user_password="", owner_password="ChaveMestra123", permissions_flag=4)
                    with open(pdf_final_caminho, "wb") as f:
                        escritor.write(f)
                        
                    with open(pdf_final_caminho, "rb") as f_final:
                        st.session_state.pdf_final_bytes = f_final.read()
                    st.rerun()

    with col4:
        st.subheader("Status do Documento")
        todos_assinaram = all(a["status"] == "Assinado" for a in st.session_state.banco_dados["assinantes"]) if st.session_state.banco_dados["assinantes"] else False
        
        if "pdf_final_bytes" in st.session_state:
            if todos_assinaram:
                st.
