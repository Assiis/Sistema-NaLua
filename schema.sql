CREATE TABLE IF NOT EXISTS produtos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(120) NOT NULL UNIQUE,
    quantidade INTEGER NOT NULL DEFAULT 0 CHECK (quantidade >= 0),
    custo_unitario NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (custo_unitario >= 0),
    preco_venda NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (preco_venda >= 0),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vendas (
    id SERIAL PRIMARY KEY,
    data_hora TIMESTAMP NOT NULL DEFAULT NOW(),
    total_venda NUMERIC(12, 2) NOT NULL,
    total_custo NUMERIC(12, 2) NOT NULL,
    total_lucro NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS itens_venda (
    id SERIAL PRIMARY KEY,
    venda_id INTEGER NOT NULL REFERENCES vendas(id) ON DELETE CASCADE,
    produto_id INTEGER REFERENCES produtos(id) ON DELETE SET NULL,
    nome_produto VARCHAR(120) NOT NULL,
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    custo_unitario NUMERIC(12, 2) NOT NULL,
    preco_unitario NUMERIC(12, 2) NOT NULL,
    lucro_unitario NUMERIC(12, 2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vendas_data_hora ON vendas (data_hora);
CREATE INDEX IF NOT EXISTS idx_itens_venda_produto ON itens_venda (produto_id);
