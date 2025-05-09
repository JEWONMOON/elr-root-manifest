import os

def load_memory_context(memory_folder="memory/"):
    """Reads and aggregates all .txt memory files into a single context string."""
    context = ""
    if not os.path.exists(memory_folder):
        return "(No memory found)"
    for fname in sorted(os.listdir(memory_folder)):
        if fname.endswith(".txt"):
            with open(os.path.join(memory_folder, fname), 'r', encoding='utf-8') as f:
                context += f"\n[f:{fname}]\n" + f.read()
    return context