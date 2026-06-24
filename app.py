# --- PROCESSAR ENTRADA DE LOTE ---
def criador_processa_lote(arquivo_pdf, texto_assinantes, meu_email, minha_senha_app, link_sistema):
    if arquivo_pdf is None:
        return st.error("ERRO: Anexe um arquivo PDF.")
    if not texto_assinantes.strip():
        return st.error("ERRO: Insira pelo menos 1 assinante.")
    if not meu_email or not minha_senha_app:
        return st.error("ERRO: Configure suas credenciais de e-mail.")
    if not link_sistema.strip():
        return st.error("ERRO: Insira o link do seu sistema para enviar aos assinantes.")

    st.session_state.banco_dados["caminho_original"] = arquivo_pdf.name
    st.session_state.banco_dados["conteudo_original"] = arquivo_pdf.getvalue()
    st.session_state.banco_dados["assinantes"] = []
    
    hasher = hashlib.sha256()
    hasher.update(st.session_state.banco_dados["conteudo_original"])
    st.session_state.banco_dados["hash_seguranca"] = hasher.hexdigest()

    linhas = texto_assinantes.strip().split("\n")
    emails_enviados = 0
    linhas_ignoradas = 0
    
    for linha in linhas:
        if ";" in linha:
            partes = line = linha.split(";")
            nome = partes[0].strip()
            email = partes[1].strip()
            token = secrets.token_hex(4)
            
            st.session_state.banco_dados["assinantes"].append({
                "nome": nome, "email": email, "token": token,
                "cpf": "", "status": "Pendente", "data": "-"
            })
            
            sucesso = enviar_email_individual(meu_email, minha_senha_app, email, nome, link_sistema)
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
