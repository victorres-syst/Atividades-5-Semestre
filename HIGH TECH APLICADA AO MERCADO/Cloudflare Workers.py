import os
import requests
import json
import time
from google.colab import userdata

# 1. Recupera as credenciais cadastradas nos Secrets do Colab[cite: 1]
CF_ACCOUNT_ID = userdata.get("CF_ACCOUNT_ID")
CF_API_TOKEN  = userdata.get("CF_API_TOKEN")

BASE = "https://api.cloudflare.com/client/v4"
HDR  = {"Authorization": f"Bearer {CF_API_TOKEN}"}

WORKER_NAME = "desafio-estoque"

# 2. Escreve o Worker em JavaScript
worker_script = '''
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Tratamento de requisições POST para salvar/atualizar estoque
    if (request.method === "POST") {
      try {
        const body = await request.json();
        if (!body.item) {
          return new Response(JSON.stringify({ error: "Envie um JSON com a chave 'item'" }), { status: 400 });
        }
        
        const item = body.item;
        const quantidade = body.quantidade ? String(body.quantidade) : "10";
        
        // Salva no KV do estoque[cite: 1]
        await env.ESTOQUE.put(item, quantidade);
        
        return new Response(JSON.stringify({ 
          mensagem: "Item cadastrado com sucesso!", 
          item: item, 
          quantidade: quantidade 
        }), { status: 201, headers: { "Content-Type": "application/json" } });
        
      } catch (e) {
        return new Response(JSON.stringify({ error: "JSON inválido" }), { status: 400 });
      }
    }

    // Tratamento de requisições GET /{item} para ler o estoque[cite: 1]
    if (request.method === "GET") {
      const itemKey = path.replace("/", "").trim();
      
      if (!itemKey) {
        return new Response(JSON.stringify({ info: "Informe o nome do item na URL. Ex: GET /caneta" }), { status: 400 });
      }

      // Consulta o item salvo no KV[cite: 1]
      const quantidade = await env.ESTOQUE.get(itemKey);

      if (quantidade === null) {
        return new Response(JSON.stringify({ error: "Item não encontrado no estoque" }), { status: 404 });
      }

      return new Response(JSON.stringify({ item: itemKey, quantidade: quantidade }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    return new Response(JSON.stringify({ error: "Método não suportado" }), { status: 405 });
  }
};
'''

# 3. Faz o deploy do script do Worker via API
print("🚀 Realizando deploy do Worker...")
r = requests.put(
    f"{BASE}/accounts/{CF_ACCOUNT_ID}/workers/scripts/{WORKER_NAME}",
    headers={**HDR, "Content-Type": "application/javascript"},
    data=worker_script,
)
print("Status Deploy:", r.status_code)

# 4. Cria o Namespace KV 'estoque-kv'
print("\n📦 Criando Namespace KV...")
r_kv = requests.post(
    f"{BASE}/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces",
    headers={**HDR, "Content-Type": "application/json"},
    json={"title": "estoque-kv"},
)
resp_kv = r_kv.json()

if resp_kv.get("success"):
    ESTOQUE_KV_ID = resp_kv["result"]["id"]
else:
    listing = requests.get(f"{BASE}/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces", headers=HDR).json().get("result", [])
    match = [n for n in listing if n["title"] == "estoque-kv"]
    ESTOQUE_KV_ID = match[0]["id"] if match else None

print(f"✔ KV ID: {ESTOQUE_KV_ID}")

# 5. Vincula o Namespace ao Worker sob o nome "ESTOQUE"[cite: 1]
binding = {
    "kv_namespaces": [
        {"binding": "ESTOQUE", "namespace_id": ESTOQUE_KV_ID}
    ]
}
requests.put(
    f"{BASE}/accounts/{CF_ACCOUNT_ID}/workers/scripts/{WORKER_NAME}/bindings",
    headers={**HDR, "Content-Type": "application/json"},
    json=binding,
)
print("✔ Binding vinculada com sucesso!")

# 6. Testando as rotas do Worker
# IMPORTANTE: Substitua 'SEU_SUBDOMINIO' pelo seu subdomínio do Workers dev[cite: 1]
WORKER_SUBDOMAIN = "SEU_SUBDOMINIO" 
BASE_URL = f"https://{WORKER_NAME}.{WORKER_SUBDOMAIN}.workers.dev"

if WORKER_SUBDOMAIN != "SEU_SUBDOMINIO":
    print(f"\n🧪 Testando a API na URL: {BASE_URL}")

    # Teste 1: POST para salvar um item
    print("\n1. Cadastrando 'caneta' no estoque via POST...")
    resp_post = requests.post(
        BASE_URL, 
        json={"item": "caneta", "quantidade": "15"}
    )
    print("Status:", resp_post.status_code)
    print("Resposta:", resp_post.text)

    # Aguarda propagação do KV
    time.sleep(1)

    # Teste 2: GET /{item} para recuperar o estoque
    print("\n2. Consultando 'caneta' no estoque via GET...")
    resp_get = requests.get(f"{BASE_URL}/caneta")
    print("Status:", resp_get.status_code)
    print("Resposta:", resp_get.text)
else:
    print("\n⚠️ Altere a variável 'WORKER_SUBDOMAIN' para o seu subdomínio para testar as requisições na URL pública!")