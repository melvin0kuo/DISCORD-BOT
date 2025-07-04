import os
import faiss
import numpy as np
import pickle
from typing import List, Tuple, Dict, Optional

class VectorDB:
    def __init__(self, db_path="vector_db"):
        self.db_path = db_path
        self.index_path = os.path.join(db_path, "faiss.index")
        self.meta_path = os.path.join(db_path, "meta.pkl")
        self.dim = 768  # 預設 embedding 維度，可依模型調整
        self.index = faiss.IndexFlatL2(self.dim)
        self.meta: List[Dict] = []  # [{user_id, channel_id, text, embedding}]
        if not os.path.exists(db_path):
            os.makedirs(db_path)
        self._load()

    def add(self, user_id: str, channel_id: str, text: str, embedding: np.ndarray):
        assert embedding.shape == (self.dim,)
        self.index.add(np.expand_dims(embedding, 0))
        self.meta.append({
            "user_id": user_id,
            "channel_id": channel_id,
            "text": text
        })
        self._save()

    def search(self, user_id: Optional[str], channel_id: Optional[str], embedding: np.ndarray, top_k=5) -> List[Dict]:
        if self.index.ntotal == 0:
            return []
        D, I = self.index.search(np.expand_dims(embedding, 0), top_k)
        results = []
        for idx in I[0]:
            if idx < len(self.meta):
                m = self.meta[idx]
                if (user_id is None or m["user_id"] == user_id) and (channel_id is None or m["channel_id"] == channel_id):
                    results.append(m)
        return results

    def _save(self):
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "wb") as f:
            pickle.dump(self.meta, f)

    def _load(self):
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "rb") as f:
                self.meta = pickle.load(f)