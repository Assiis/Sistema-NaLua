from supabase import create_client, Client

class SistemaEstoqueSupabase:
    def __init__(self, supabase_url, supabase_key):
        # 1. Conecta seu programa direto na nuvem do Supabase!
        self.supabase: Client = create_client(supabase_url, supabase_key)
        print("✅ Conectado à nuvem do Supabase com sucesso!")

    # FASE 1: COMPRAS
    def comprar_ingrediente(self, nome, quantidade, valor_total):
        custo_unitario = valor_total / quantidade
        
        # 1. Registra a saída do dinheiro na tabela financeira
        self.supabase.table("financeiro").insert({
            "tipo": "SAIDA", 
            "descricao": f"Compra: {nome}", 
            "valor": valor_total
        }).execute()
        
        # 2. Verifica se o ingrediente já existe no estoque
        busca = self.supabase.table("estoque_base").select("*").eq("nome", nome).execute()
        
        if len(busca.data) > 0:
            # Se existe, soma a quantidade nova com a velha
            qtd_atual = busca.data[0]['quantidade']
            nova_qtd = qtd_atual + quantidade
            self.supabase.table("estoque_base").update({"quantidade": nova_qtd}).eq("nome", nome).execute()
        else:
            # Se não existe, cria um novo
            self.supabase.table("estoque_base").insert({
                "nome": nome, 
                "quantidade": quantidade, 
                "custo_unitario": custo_unitario
            }).execute()
            
        print(f"🛒 COMPRA REGISTRADA NA NUVEM: {quantidade}x {nome}")

    # FASE 3: VENDAS (A Fase 2 de Produção segue a mesma lógica lógica de busca e update)
    def vender_doce(self, nome_doce, quantidade, preco_venda_unidade):
        # 1. Busca o doce no estoque
        busca = self.supabase.table("estoque_pronto").select("*").eq("nome", nome_doce).execute()
        
        if len(busca.data) > 0 and busca.data[0]['quantidade'] >= quantidade:
            # 2. Tira do estoque
            nova_qtd = busca.data[0]['quantidade'] - quantidade
            self.supabase.table("estoque_pronto").update({"quantidade": nova_qtd}).eq("nome", nome_doce).execute()
            
            # 3. Registra a entrada do dinheiro
            valor_venda = quantidade * preco_venda_unidade
            self.supabase.table("financeiro").insert({
                "tipo": "ENTRADA", 
                "descricao": f"Venda: {quantidade}x {nome_doce}", 
                "valor": valor_venda
            }).execute()
            
            print(f"💰 VENDA SALVA NA NUVEM: R$ {valor_venda:.2f}")
        else:
            print(f"❌ ERRO: Faltou {nome_doce} no estoque para vender.")


# ==========================================
# TESTANDO A CONEXÃO
# ==========================================
URL = "sua_url_aqui_exemplo.supabase.co"
CHAVE = "sua_chave_secreta_gigante_aqui"

# meu_sistema = SistemaEstoqueSupabase(URL, CHAVE)
# meu_sistema.comprar_ingrediente("Leite Condensado", 10, 50.00)
# meu_sistema.vender_doce("Chup-chup de Chocolate", 5, 4.00)