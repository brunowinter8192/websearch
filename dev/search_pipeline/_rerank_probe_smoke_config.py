# INFRASTRUCTURE
from bm25_sweep_smoke import VANILLA_K1

QUERY_CATEGORIES: dict[str, str] = {
    "bert fine-tuning natural language processing":              "academic",
    "knowledge graph embedding relational learning":             "academic",
    "contrastive learning self-supervised representations":      "academic",
    "variational autoencoder latent space generative model":     "academic",
    "graph neural network node classification":                  "academic",
    "best espresso machine under 500 2026":                      "product",
    "mechanical keyboard switches comparison tactile linear":    "product",
    "best noise cancelling headphones 2026":                     "product",
    "standing desk ergonomics home office":                      "product",
    "air fryer vs convection oven cooking":                      "product",
    "python asyncio event loop concurrency":                     "technical",
    "rust ownership borrowing lifetime explained":               "technical",
    "docker compose network bridge host mode":                   "technical",
    "postgresql index types btree gin gist performance":         "technical",
    "react useEffect cleanup subscription pattern":              "technical",
    "transformer attention mechanism":                           "mixed_pathology",
    "neural network activation functions comparison":            "mixed_pathology",
    "gradient descent optimization methods stochastic":          "mixed_pathology",
    "protein structure prediction alphafold deep learning":      "mixed_pathology",
    "convolutional neural network image classification tutorial": "mixed_pathology",
}

TOP_N       = 10
RETRIEVE_N  = 50
BM25_K1     = VANILLA_K1
BM25_B      = 0.75
BM25_SW     = True
BM25_REPR   = "title+snippet"

EMBEDDING_URL = "http://127.0.0.1:8084/v1/embeddings"
RERANKER_URL  = "http://127.0.0.1:8082/v1/rerank"
