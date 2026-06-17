#!/bin/bash
# install-odoo-mcp.sh
#
# Installe le module MCP Server (addon Odoo + client Python mcp-server-odoo)
# sur le serveur Odoo 19 ubuntu@98.86.240.145 (clone sovap, neutralisé).
#
# Ce que fait ce script :
#   1. Installe defusedxml dans le venv Odoo
#   2. Copie et extrait l'addon mcp_server dans /opt/odoo19/extra-addons/
#      (répertoire hors du repo git /opt/odoo19/odoo)
#   3. Ajoute extra-addons au addons_path dans /etc/odoo.conf
#   4. Installe le module via odoo-bin --stop-after-init -i mcp_server
#   5. Redémarre Odoo
#   6. Active le MCP globalement via res.config.settings
#   7. Active les modèles Odoo accessibles via MCP
#   8. Génère une clé API pour l'utilisateur admin
#   9. Installe le client Python mcp-server-odoo dans /opt/mcp-server-odoo/
#  10. Crée le fichier .env et le wrapper /usr/local/bin/mcp-server-odoo
#  11. Teste le serveur MCP en stdio
#  12. Affiche la config .mcp.json pour Claude Code
#
# Prérequis :
#   - Le fichier zip de l'addon : addons/mcp_server-19.0.1.0.0.zip
#   - Accès SSH avec la clé ~/certs/key_database.pem
#   - L'utilisateur admin Odoo avec son mot de passe (--admin-password)
#
# Usage :
#   ./scripts/install-odoo-mcp.sh \
#     --admin-login md@maximedesmaraistechnologies.com \
#     --admin-password <mot_de_passe>
#
#   Si --admin-password est omis, le script réinitialise le mot de passe
#   admin à la valeur de --new-admin-password (défaut: mcp_admin_2026)

set -euo pipefail

# ── Paramètres par défaut ───────────────────────────────────────────────────
SSH_KEY="${HOME}/certs/key_database.pem"
SSH_HOST="ubuntu@98.86.240.145"
ODOO_URL="http://localhost:8069"
ODOO_DB="sovap"
ODOO_VENV="/opt/odoo19/venv"
ODOO_BIN="/opt/odoo19/odoo/odoo/odoo-bin"
ODOO_CONF="/etc/odoo.conf"
ODOO_USER="odoo"          # utilisateur système Odoo
EXTRA_ADDONS="/opt/odoo19/extra-addons"
MCP_INSTALL="/opt/mcp-server-odoo"
ADDON_ZIP="$(dirname "$0")/../addons/mcp_server-19.0.1.0.0.zip"

# Identifiants admin Odoo
ADMIN_LOGIN="md@maximedesmaraistechnologies.com"
ADMIN_PASSWORD=""
NEW_ADMIN_PASSWORD="mcp_admin_2026"

# Modèles à activer dans MCP (lecture + écriture, sans suppression)
MCP_MODELS=(
    "res.partner"
    "res.users"
    "product.product"
    "product.template"
    "sale.order"
    "sale.order.line"
    "account.move"
    "account.move.line"
    "stock.picking"
    "mrp.production"
    "project.project"
    "project.task"
)

# ── Parsing des arguments ───────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --admin-login)       ADMIN_LOGIN="$2"; shift ;;
        --admin-password)    ADMIN_PASSWORD="$2"; shift ;;
        --new-admin-password) NEW_ADMIN_PASSWORD="$2"; shift ;;
        --ssh-key)           SSH_KEY="$2"; shift ;;
        --ssh-host)          SSH_HOST="$2"; shift ;;
        --addon-zip)         ADDON_ZIP="$2"; shift ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Argument inconnu : $1" >&2; exit 1 ;;
    esac
    shift
done

# ── Validation ──────────────────────────────────────────────────────────────
if [[ ! -f "$SSH_KEY" ]]; then
    echo "ERREUR : Clé SSH introuvable : $SSH_KEY" >&2
    exit 1
fi

ADDON_ZIP="$(realpath "$ADDON_ZIP" 2>/dev/null || echo "$ADDON_ZIP")"
if [[ ! -f "$ADDON_ZIP" ]]; then
    echo "ERREUR : Zip de l'addon introuvable : $ADDON_ZIP" >&2
    echo "Préciser le chemin avec --addon-zip <fichier.zip>" >&2
    exit 1
fi

SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $SSH_HOST"

echo "========================================================"
echo " Installation MCP Server Odoo 19"
echo " Serveur : $SSH_HOST"
echo " Addon   : $(basename "$ADDON_ZIP")"
echo "========================================================"

# ── Étape 1 : defusedxml + répertoire extra-addons ─────────────────────────
echo ""
echo "--- [1/10] defusedxml + répertoire extra-addons ---"
$SSH bash << REMOTE
set -euo pipefail
sudo $ODOO_VENV/bin/pip install --quiet defusedxml
echo "defusedxml : \$($ODOO_VENV/bin/pip show defusedxml | grep Version)"
sudo mkdir -p $EXTRA_ADDONS
sudo chown $ODOO_USER:$ODOO_USER $EXTRA_ADDONS
sudo chmod 755 $EXTRA_ADDONS
# Installer unzip si absent
command -v unzip >/dev/null || sudo apt-get install -y unzip -qq
echo "Répertoire $EXTRA_ADDONS : OK"
REMOTE

# ── Étape 2 : copier et extraire l'addon ───────────────────────────────────
echo ""
echo "--- [2/10] Copie et extraction de l'addon ---"
scp -i "$SSH_KEY" "$ADDON_ZIP" "$SSH_HOST:/tmp/mcp_addon.zip"
$SSH bash << REMOTE
set -euo pipefail
# Supprimer l'ancienne version si présente
sudo rm -rf $EXTRA_ADDONS/mcp_server
sudo unzip -q /tmp/mcp_addon.zip -d $EXTRA_ADDONS/
sudo chown -R $ODOO_USER:$ODOO_USER $EXTRA_ADDONS/mcp_server
echo "Addon extrait dans $EXTRA_ADDONS/mcp_server : OK"
rm -f /tmp/mcp_addon.zip
REMOTE

# ── Étape 3 : addons_path dans /etc/odoo.conf ──────────────────────────────
echo ""
echo "--- [3/10] Ajout de extra-addons au addons_path ---"
$SSH bash << REMOTE
set -euo pipefail
if sudo grep -q "$EXTRA_ADDONS" $ODOO_CONF; then
    echo "addons_path contient déjà $EXTRA_ADDONS"
else
    sudo sed -i "s|addons_path = .*|&,$EXTRA_ADDONS|" $ODOO_CONF
    echo "addons_path mis à jour : OK"
fi
sudo grep 'addons_path' $ODOO_CONF
REMOTE

# ── Étape 4 : réinitialiser le mot de passe admin si nécessaire ────────────
echo ""
echo "--- [4/10] Vérification / réinitialisation du mot de passe admin ---"
if [[ -z "$ADMIN_PASSWORD" ]]; then
    echo "Pas de --admin-password fourni → réinitialisation à '$NEW_ADMIN_PASSWORD'"
    $SSH bash << REMOTE
set -euo pipefail
sudo systemctl stop odoo19
sudo -u $ODOO_USER $ODOO_VENV/bin/python3 $ODOO_BIN shell \
  -c $ODOO_CONF -d $ODOO_DB --no-http 2>/dev/null << 'PYEOF'
user = env['res.users'].browse(2)
user.password = '$NEW_ADMIN_PASSWORD'
env.cr.commit()
print(f'Mot de passe réinitialisé pour : {user.login}')
quit()
PYEOF
sudo systemctl start odoo19 && sleep 7
REMOTE
    ADMIN_PASSWORD="$NEW_ADMIN_PASSWORD"
fi

# ── Étape 5 : installer le module via odoo-bin ─────────────────────────────
echo ""
echo "--- [5/10] Installation du module mcp_server ---"
$SSH bash << REMOTE
set -euo pipefail
# Vérifier si déjà installé
INSTALLED=\$(PGPASSWORD=\$(sudo grep 'db_password' $ODOO_CONF | cut -d= -f2 | tr -d ' ') \
  psql -h localhost -U \$(sudo grep 'db_user' $ODOO_CONF | cut -d= -f2 | tr -d ' ') \
  -d $ODOO_DB -tAc "SELECT state FROM ir_module_module WHERE name='mcp_server';" 2>/dev/null || echo "")
if [[ "\$INSTALLED" == "installed" ]]; then
    echo "Module mcp_server déjà installé — mise à jour..."
    sudo systemctl stop odoo19
    sudo -u $ODOO_USER $ODOO_VENV/bin/python3 $ODOO_BIN \
      -c $ODOO_CONF -d $ODOO_DB --stop-after-init -u mcp_server 2>&1 | grep -E 'mcp_server|ERROR' | tail -5
else
    echo "Installation du module mcp_server..."
    sudo systemctl stop odoo19
    sudo -u $ODOO_USER $ODOO_VENV/bin/python3 $ODOO_BIN \
      -c $ODOO_CONF -d $ODOO_DB --stop-after-init -i mcp_server 2>&1 | grep -E 'mcp_server|ERROR' | tail -5
fi
sudo systemctl start odoo19 && sleep 7
echo "État du module :"
PGPASSWORD=\$(sudo grep 'db_password' $ODOO_CONF | cut -d= -f2 | tr -d ' ') \
  psql -h localhost -U \$(sudo grep 'db_user' $ODOO_CONF | cut -d= -f2 | tr -d ' ') \
  -d $ODOO_DB -c "SELECT name, state, latest_version FROM ir_module_module WHERE name='mcp_server';"
REMOTE

# ── Étape 6 : activer MCP globalement + modèles ────────────────────────────
echo ""
echo "--- [6/10] Activation MCP + modèles ---"
MODELS_JSON=$(printf '"%s",' "${MCP_MODELS[@]}")
MODELS_JSON="[${MODELS_JSON%,}]"

$SSH bash << REMOTE
set -euo pipefail
sudo -u $ODOO_USER $ODOO_VENV/bin/python3 - << 'PYEOF'
import xmlrpc.client, json, sys

url, db = '$ODOO_URL', '$ODOO_DB'
username, password = '$ADMIN_LOGIN', '$ADMIN_PASSWORD'
mcp_models = $MODELS_JSON

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
if not uid:
    print('ERREUR: authentification échouée', file=sys.stderr)
    sys.exit(1)
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Activer MCP globalement
cfg_id = models.execute_kw(db, uid, password, 'res.config.settings', 'create', [{
    'mcp_enabled': True,
    'mcp_enable_logging': True,
    'mcp_enable_rate_limiting': False,
}])
models.execute_kw(db, uid, password, 'res.config.settings', 'execute', [[cfg_id]])
print('MCP activé globalement : OK')

# Activer les modèles
for model_name in mcp_models:
    ids = models.execute_kw(db, uid, password, 'ir.model', 'search', [[['model','=',model_name]]])
    if not ids:
        print(f'  SKIP (inexistant): {model_name}')
        continue
    existing = models.execute_kw(db, uid, password, 'mcp.enabled.model', 'search', [[['model_name','=',model_name]]])
    if existing:
        print(f'  DÉJÀ actif: {model_name}')
        continue
    rec_id = models.execute_kw(db, uid, password, 'mcp.enabled.model', 'create', [{
        'model_id': ids[0], 'allow_read': True, 'allow_write': True,
        'allow_create': True, 'allow_unlink': False,
    }])
    print(f'  ACTIVÉ (id={rec_id}): {model_name}')
PYEOF
REMOTE

# ── Étape 7 : générer la clé API ───────────────────────────────────────────
echo ""
echo "--- [7/10] Génération de la clé API ---"
$SSH bash << REMOTE
set -euo pipefail
# Vérifier si une clé mcp-server-claude existe déjà
EXISTING_KEY=\$(PGPASSWORD=\$(sudo grep 'db_password' $ODOO_CONF | cut -d= -f2 | tr -d ' ') \
  psql -h localhost -U \$(sudo grep 'db_user' $ODOO_CONF | cut -d= -f2 | tr -d ' ') \
  -d $ODOO_DB -tAc \
  "SELECT index FROM res_users_apikeys WHERE name='mcp-server-claude' LIMIT 1;" 2>/dev/null || echo "")
if [[ -n "\$EXISTING_KEY" ]]; then
    echo "Clé API 'mcp-server-claude' déjà présente (index: \$EXISTING_KEY)"
    echo "Pour régénérer, supprimer manuellement la clé dans Odoo puis relancer ce script."
else
    sudo systemctl stop odoo19
    MCP_API_KEY=\$(sudo -u $ODOO_USER $ODOO_VENV/bin/python3 $ODOO_BIN shell \
      -c $ODOO_CONF -d $ODOO_DB --no-http 2>/dev/null << 'PYEOF'
user = env['res.users'].browse(2)
key = env['res.users.apikeys'].with_user(user).sudo()._generate(None, 'mcp-server-claude', None)
env.cr.commit()
print(f'API_KEY={key}')
quit()
PYEOF
)
    echo "\$MCP_API_KEY"
    sudo systemctl start odoo19 && sleep 7
fi
REMOTE

# ── Étape 8 : installer le client Python mcp-server-odoo ───────────────────
echo ""
echo "--- [8/10] Installation du client Python mcp-server-odoo ---"
$SSH bash << REMOTE
set -euo pipefail
if [[ -d "$MCP_INSTALL/.git" ]]; then
    git -C "$MCP_INSTALL" pull --ff-only
else
    git clone https://github.com/ivnvxd/mcp-server-odoo.git "$MCP_INSTALL"
fi
if [[ ! -d "$MCP_INSTALL/venv" ]]; then
    python3 -m venv "$MCP_INSTALL/venv"
fi
"$MCP_INSTALL/venv/bin/pip" install --quiet --upgrade pip
"$MCP_INSTALL/venv/bin/pip" install --quiet "$MCP_INSTALL"
echo "Version: \$("$MCP_INSTALL/venv/bin/pip" show mcp-server-odoo | grep ^Version)"
REMOTE

# ── Étape 9 : .env + wrapper ───────────────────────────────────────────────
echo ""
echo "--- [9/10] Fichier .env et wrapper /usr/local/bin/mcp-server-odoo ---"

# Récupérer la clé API depuis la BDD
API_KEY=$($SSH bash << REMOTE
PGPASSWORD=\$(sudo grep 'db_password' $ODOO_CONF | cut -d= -f2 | tr -d ' ') \
  psql -h localhost -U \$(sudo grep 'db_user' $ODOO_CONF | cut -d= -f2 | tr -d ' ') \
  -d $ODOO_DB -tAc \
  "SELECT index FROM res_users_apikeys WHERE name='mcp-server-claude' LIMIT 1;" 2>/dev/null || echo ""
REMOTE
)

# Écrire le .env (la clé API est écrite telle quelle depuis l'étape 7)
$SSH bash << REMOTE
set -euo pipefail
# Récupérer la clé complète depuis la table (index seulement si clé déjà existante)
# La vraie clé a été affichée par étape 7 — ici on écrit ce qu'on a
cat > "$MCP_INSTALL/.env" << 'ENVEOF'
# mcp-server-odoo — Mode standard (addon mcp_server installé dans Odoo)
# Généré par install-odoo-mcp.sh
ODOO_URL=$ODOO_URL
ODOO_DB=$ODOO_DB
ODOO_USER=$ADMIN_LOGIN
ODOO_YOLO=off
ODOO_LOCALE=fr_FR
ODOO_MCP_LOG_LEVEL=INFO
ODOO_MCP_DEFAULT_LIMIT=20
ODOO_MCP_MAX_LIMIT=200
ENVEOF
echo "ODOO_API_KEY=REMPLACER_PAR_LA_CLE_AFFICHEE_ETAPE_7" >> "$MCP_INSTALL/.env"
echo ".env écrit dans $MCP_INSTALL/.env"
echo "(Remplacer ODOO_API_KEY manuellement si la clé a été générée à l'étape 7)"

# Créer le wrapper
sudo tee /usr/local/bin/mcp-server-odoo > /dev/null << 'WRAPEOF'
#!/bin/bash
set -a
source /opt/mcp-server-odoo/.env
set +a
exec /opt/mcp-server-odoo/venv/bin/mcp-server-odoo "\$@"
WRAPEOF
sudo chmod +x /usr/local/bin/mcp-server-odoo
echo "Wrapper /usr/local/bin/mcp-server-odoo : OK"
REMOTE

# ── Étape 10 : test MCP ────────────────────────────────────────────────────
echo ""
echo "--- [10/10] Test du serveur MCP ---"
$SSH bash << REMOTE
API_KEY=\$(grep ODOO_API_KEY $MCP_INSTALL/.env | cut -d= -f2)
echo "Health check :"
curl -s http://localhost:8069/mcp/health
echo ""
echo "Auth validate :"
curl -s http://localhost:8069/mcp/auth/validate -H "X-API-Key: \$API_KEY"
echo ""
REMOTE

# ── Résumé final ───────────────────────────────────────────────────────────
EIGENT_API="https://ai.steamocloud.com/api"
MCP_COMMAND="ssh"
MCP_ARGS="[\"-i\", \"${SSH_KEY}\", \"-o\", \"StrictHostKeyChecking=no\", \"-o\", \"BatchMode=yes\", \"${SSH_HOST}\", \"mcp-server-odoo\"]"

echo ""
echo "========================================================"
echo " Ajout dans Eigent"
echo "========================================================"
cat << EIGENT

─── Option A : via l'API Eigent (nécessite un token d'authentification) ───

  1. Récupérer votre token Eigent (session stackauth ou JWT) :
       curl -s -X POST ${EIGENT_API}/user/login \\
         -H 'Content-Type: application/json' \\
         -d '{"email":"...","password":"..."}' | jq -r '.data.token'

  2. Importer le MCP dans Eigent :
       curl -s -X POST '${EIGENT_API}/mcp/import/local' \\
         -H 'Content-Type: application/json' \\
         -H 'Authorization: Bearer <TOKEN>' \\
         -d '{
           "mcpServers": {
             "odoo": {
               "command": "${MCP_COMMAND}",
               "args": ${MCP_ARGS}
             }
           }
         }'

─── Option B : depuis l'interface Eigent ─────────────────────────────────

  Paramètres > MCP Servers > Importer > Local
  Coller le JSON suivant :

  {
    "mcpServers": {
      "odoo": {
        "command": "${MCP_COMMAND}",
        "args": ${MCP_ARGS}
      }
    }
  }

─── Option C : Claude Code (.mcp.json à la racine du projet) ─────────────

  {
    "mcpServers": {
      "odoo": {
        "command": "${MCP_COMMAND}",
        "args": ${MCP_ARGS}
      }
    }
  }

  Ou via la CLI :
    claude mcp add odoo -- ssh -i ${SSH_KEY} \\
      -o StrictHostKeyChecking=no ${SSH_HOST} mcp-server-odoo

──────────────────────────────────────────────────────────────────────────

IMPORTANT : Vérifier que ODOO_API_KEY dans ${SSH_HOST}:${MCP_INSTALL}/.env
contient la vraie clé affichée à l'étape 7 (ligne API_KEY=...).

EIGENT
