# Antes de tudo: runtime do Visual C++ do sistema, para o torch funcionar no Windows com Python
# do Anaconda (ver src/utils/torch_windows.py). Tem de ser o PRIMEIRO código do pacote (o protótipo usa a mesma função): qualquer
# extensão em C++ importada antes fixaria o runtime antigo. No-op fora do Windows.
from src.utils.torch_windows import carregar_runtime_do_sistema as _carregar_runtime

_carregar_runtime()
