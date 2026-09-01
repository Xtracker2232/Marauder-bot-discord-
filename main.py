import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import aiohttp
import io
from datetime import datetime
import os
import asyncio

# ============================================
# VARIABLES D'ENVIRONNEMENT (RAILWAY)
# ============================================
TOKEN = os.getenv('DISCORD_TOKEN')
BRIX_KEY = os.getenv('BRIX_KEY')
API_URL = os.getenv('API_URL', "https://marauder.host")
BRIX_API_URL = os.getenv('BRIX_API_URL', "https://api.brixhub.to/api/v1")

TICKET_CHANNEL_ID = int(os.getenv('TICKET_CHANNEL_ID', 0))
RULES_CHANNEL_ID = int(os.getenv('RULES_CHANNEL_ID', 0))
STAFF_ROLE_ID = int(os.getenv('STAFF_ROLE_ID', 0))
OWNER_ROLE_ID = int(os.getenv('OWNER_ROLE_ID', 0))
MEMBER_ROLE_ID = int(os.getenv('MEMBER_ROLE_ID', 0))

if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN non défini !")
if not BRIX_KEY:
    raise ValueError("❌ BRIX_KEY non défini !")

# ============================================
# INTENTS
# ============================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ============================================
# CONFIGURATION
# ============================================
MAX_RESULTS = 10
PANEL_COLOR = 0x6366f1
LOGO_URL = "https://cdn.discordapp.com/attachments/1477415267452719208/1543881553220997240/favicon-32x32.png"

# ============================================
# STATS
# ============================================
bot_stats = {"searches": 0, "users": set()}

# ============================================
# VÉRIFICATION DES RÔLES
# ============================================

def has_owner_role(interaction):
    if not interaction.guild:
        return False
    role = interaction.guild.get_role(OWNER_ROLE_ID)
    return role and role in interaction.user.roles

def has_staff_role(interaction):
    if not interaction.guild:
        return False
    role = interaction.guild.get_role(STAFF_ROLE_ID)
    return role and role in interaction.user.roles

def has_permission(interaction):
    return has_staff_role(interaction) or has_owner_role(interaction)

def is_ticket_channel(channel):
    return channel.name.startswith("ticket-")

# ============================================
# API BRIX
# ============================================

async def brix_search(payload):
    headers = {"X-API-Key": BRIX_KEY, "Content-Type": "application/json", "User-Agent": "Marauder-Bot/1.0"}
    url = f"{BRIX_API_URL}/search"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=15) as r:
            return r.status, await r.json()

async def brix_lookup(value):
    headers = {"X-API-Key": BRIX_KEY, "User-Agent": "Marauder-Bot/1.0"}
    if "@" in value:
        path = f"email/{value}"
    elif value.upper().startswith("FR") and len(value) > 15:
        path = f"iban/{value}"
    else:
        path = f"phone/{value}"
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BRIX_API_URL}/lookup/{path}", headers=headers, timeout=15) as r:
            return r.status, await r.json()

# ============================================
# FORMATAGE
# ============================================

LABELS = {
    "nom_famille": "Nom", "prenom": "Prénom", "nom_naissance": "Nom naissance",
    "nom_affichage": "Nom affiché", "nom_utilisateur": "Utilisateur",
    "genre": "Genre", "civilite": "Civilité",
    "date_naissance": "Naissance", "annee_naissance": "Année naiss.",
    "ville_naissance": "Ville naiss.", "lieu_naissance": "Lieu naiss.",
    "email": "Email", "telephone": "Téléphone", "mobile": "Mobile", "adresse_ip": "IP",
    "adresse": "Adresse", "complement_adresse": "Complément",
    "code_postal": "Code postal", "ville": "Ville",
    "pays": "Pays", "region": "Région", "departement": "Département",
    "nir": "NIR (Sécu)", "iban": "IBAN", "bic": "BIC",
    "siret": "SIRET", "siren": "SIREN",
    "vin_plaque": "VIN/Plaque", "immatriculation": "Immat.",
    "marque": "Marque", "modele": "Modèle",
    "societe": "Société", "profession": "Profession", "fonction": "Fonction",
}

def format_profile(p, index, total):
    name = " ".join(filter(None, [p.get("prenom", ""), p.get("nom_famille", "")])) or "Profil inconnu"
    lines = []
    for k, label in LABELS.items():
        v = p.get(k)
        if v and str(v).strip() and str(v) != "undefined":
            lines.append(f"**{label}** : {v}")
    sources = " · ".join(p.get("_sources", [])) or "—"
    e = discord.Embed(title=f"👤 {name}", description="\n".join(lines) or "Aucune donnée disponible", color=PANEL_COLOR)
    e.add_field(name="📂 Sources", value=sources, inline=False)
    e.set_footer(text=f"Fiche {index + 1} / {total} · Marauder Lookup")
    return e

def results_to_txt(results, query_info=""):
    lines = ["=" * 50, "MARAUDER — Résultats de recherche", "=" * 50, ""]
    if query_info:
        lines += [f"Recherche : {query_info}", ""]
    for i, p in enumerate(results):
        name = " ".join(filter(None, [p.get("prenom", ""), p.get("nom_famille", "")])) or "Profil inconnu"
        lines += [f"── Profil {i+1} : {name} ──"]
        for k, label in LABELS.items():
            v = p.get(k)
            if v and str(v).strip():
                lines.append(f"  {label} : {v}")
        sources = ", ".join(p.get("_sources", [])) or "—"
        lines += [f"  Sources : {sources}", ""]
    lines += ["=" * 50, f"Total : {len(results)} profil(s)", "=" * 50]
    return "\n".join(lines)

# ============================================
# VIEW RÉSULTATS
# ============================================

class ResultsView(View):
    def __init__(self, results, total, took, query_info="", loading_message=None):
        super().__init__(timeout=300)
        self.results = results[:MAX_RESULTS]
        self.total = total
        self.took = took
        self.query_info = query_info
        self.index = 0
        self.loading_message = loading_message
        
        self.add_item(Button(label="🌐 Site Web", style=discord.ButtonStyle.link, url=API_URL))
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.index <= 0
        self.next_btn.disabled = self.index >= len(self.results) - 1
        self.counter_btn.label = f"{self.index + 1} / {len(self.results)}"

    def current_embed(self):
        return format_profile(self.results[self.index], self.index, len(self.results))

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction, button):
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.secondary, disabled=True)
    async def counter_btn(self, interaction, button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction, button):
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="📥 Télécharger .txt", style=discord.ButtonStyle.success)
    async def download_btn(self, interaction, button):
        txt = results_to_txt(self.results, self.query_info)
        f = discord.File(io.BytesIO(txt.encode("utf-8")), filename="marauder_resultats.txt")
        await interaction.response.send_message(content="📥 Voici vos résultats :", file=f, ephemeral=True)

    @discord.ui.button(label="❌ Fermer", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction, button):
        await interaction.response.edit_message(embed=discord.Embed(title="✅ Résultats fermés", color=0x22c55e), view=None)

# ============================================
# MODALS
# ============================================

class SearchModal(Modal, title="🔍 Recherche Marauder"):
    nom = TextInput(label="Nom", placeholder="Dupont", required=False)
    prenom = TextInput(label="Prénom", placeholder="Jean", required=False)
    email = TextInput(label="Email", placeholder="jean@gmail.com", required=False)
    telephone = TextInput(label="Téléphone", placeholder="0612345678", required=False)
    ville = TextInput(label="Ville", placeholder="Paris", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = {"flexible": True, "per_page": MAX_RESULTS}
        query_parts = []
        
        if str(self.nom).strip():
            payload["nom_famille"] = str(self.nom).strip()
            query_parts.append(str(self.nom).strip())
        if str(self.prenom).strip():
            payload["prenom"] = str(self.prenom).strip()
            query_parts.append(str(self.prenom).strip())
        if str(self.email).strip():
            payload["email"] = str(self.email).strip()
            query_parts.append(str(self.email).strip())
        if str(self.telephone).strip():
            payload["telephone"] = str(self.telephone).strip()
            query_parts.append(str(self.telephone).strip())
        if str(self.ville).strip():
            payload["ville"] = str(self.ville).strip()
            query_parts.append(str(self.ville).strip())
        
        if not query_parts:
            return await interaction.followup.send(embed=discord.Embed(title="❌ Champs vides", color=0xef4444), ephemeral=True)
        
        loading = await interaction.followup.send(embed=discord.Embed(title="⏳ Recherche en cours...", color=PANEL_COLOR), ephemeral=True)
        
        status, data = await brix_search(payload)
        if status != 200:
            return await loading.edit(embed=discord.Embed(title=f"❌ Erreur API {status}", color=0xef4444))
        
        results = data.get("data", {}).get("results", [])
        if not results:
            return await loading.edit(embed=discord.Embed(title="😶 Aucun résultat", color=0xf59e0b))
        
        await loading.delete()
        view = ResultsView(results, len(results), 0, " · ".join(query_parts))
        await interaction.followup.send(embed=view.current_embed(), view=view, ephemeral=True)

class LookupModal(Modal, title="⚡ Lookup rapide"):
    value = TextInput(label="Email, téléphone ou IBAN")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loading = await interaction.followup.send(embed=discord.Embed(title="⏳ Lookup en cours...", color=PANEL_COLOR), ephemeral=True)
        
        status, data = await brix_lookup(str(self.value).strip())
        if status != 200:
            return await loading.edit(embed=discord.Embed(title=f"❌ Erreur API {status}", color=0xef4444))
        
        results = data.get("data", {}).get("results", [])
        if not results:
            return await loading.edit(embed=discord.Embed(title="😶 Aucun résultat", color=0xf59e0b))
        
        await loading.delete()
        view = ResultsView(results, len(results), 0, str(self.value).strip())
        await interaction.followup.send(embed=view.current_embed(), view=view, ephemeral=True)

# ============================================
# MAIN VIEW (PANEL)
# ============================================

class MainView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🌐 Site Web", style=discord.ButtonStyle.link, url=API_URL, row=1))

    @discord.ui.button(label="🔍 Rechercher", style=discord.ButtonStyle.primary, row=0)
    async def search(self, interaction, button):
        await interaction.response.send_modal(SearchModal())

    @discord.ui.button(label="⚡ Lookup rapide", style=discord.ButtonStyle.secondary, row=0)
    async def lookup(self, interaction, button):
        await interaction.response.send_modal(LookupModal())

# ============================================
# MODAL TICKET AVEC RAISON
# ============================================

class TicketModal(Modal, title="🎫 Nouveau ticket"):
    raison = TextInput(
        label="📌 Raison du ticket",
        placeholder="Expliquez votre demande ou problème...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        
        # Vérifier si un ticket existe déjà pour cet utilisateur
        existing = discord.utils.get(guild.channels, name=f"ticket-{interaction.user.name.lower()}")
        if existing:
            return await interaction.followup.send(
                f"❌ Vous avez déjà un ticket ouvert : {existing.mention}",
                ephemeral=True
            )
        
        ticket_channel = guild.get_channel(TICKET_CHANNEL_ID)
        if not ticket_channel:
            return await interaction.followup.send("❌ Salon de tickets introuvable.", ephemeral=True)
        
        # Créer le salon
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role_id in [STAFF_ROLE_ID, OWNER_ROLE_ID]:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name.lower()}",
            category=ticket_channel.category,
            overwrites=overwrites
        )
        
        # Embed du ticket
        embed = discord.Embed(
            title="🎫 Ticket ouvert",
            description=f"**Utilisateur :** {interaction.user.mention}\n**Raison :**\n{str(self.raison)}",
            color=PANEL_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=LOGO_URL)
        embed.set_footer(text=f"ID: {interaction.user.id}")
        
        # Seul le bouton Fermer (restreint aux staff/owner)
        await channel.send(
            embed=embed,
            view=CloseTicketView()
        )
        
        # Message de confirmation
        await interaction.followup.send(
            f"✅ Votre ticket a été créé : {channel.mention}",
            ephemeral=True
        )

# ============================================
# TICKET VIEW (Bouton pour ouvrir)
# ============================================

class TicketView(View):
    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.primary)
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TicketModal())

# ============================================
# CLOSE TICKET VIEW (Seul staff/owner peut fermer)
# ============================================

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        # Vérifier si l'utilisateur a le rôle staff ou owner
        if not has_permission(interaction):
            return await interaction.response.send_message(
                "❌ Vous n'avez pas la permission de fermer ce ticket. Seul le staff peut le faire.",
                ephemeral=True
            )
        
        if not is_ticket_channel(interaction.channel):
            return await interaction.response.send_message(
                "❌ Cette commande n'est utilisable que dans un ticket.",
                ephemeral=True
            )
        
        await interaction.response.send_message("🔒 Fermeture du ticket dans 5 secondes...")
        
        # Envoyer un message de fermeture avant de supprimer
        embed = discord.Embed(
            title="🔒 Ticket fermé",
            description=f"Fermé par {interaction.user.mention}",
            color=0xef4444
        )
        await interaction.channel.send(embed=embed)
        
        await asyncio.sleep(5)
        await interaction.channel.delete()

# ============================================
# RÈGLEMENT
# ============================================

class RulesView(View):
    @discord.ui.button(label="✅ J'accepte le règlement", style=discord.ButtonStyle.success)
    async def accept_rules(self, interaction, button):
        role = interaction.guild.get_role(MEMBER_ROLE_ID)
        if not role:
            return await interaction.response.send_message("❌ Rôle introuvable.", ephemeral=True)
        if role in interaction.user.roles:
            return await interaction.response.send_message("✅ Tu as déjà accepté le règlement.", ephemeral=True)
        
        await interaction.user.add_roles(role, reason="Règlement accepté")
        
        embed = discord.Embed(
            title="✅ Règlement accepté !",
            description=f"Bienvenue sur Marauder ! Tu as obtenu le rôle {role.mention}. 🚀",
            color=0x22c55e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================
# COMMANDES SLASH
# ============================================

@bot.tree.command(name="panel", description="Afficher le panel Marauder")
async def panel(interaction):
    embed = discord.Embed(title="**Marauder Lookup**", color=PANEL_COLOR)
    embed.set_image(url="https://cdn.discordapp.com/attachments/1477415267452719208/1529531032720904202/image.png")
    embed.set_footer(text="Created by Index")
    await interaction.response.send_message(embed=embed, view=MainView())

@bot.tree.command(name="ticket", description="Envoyer le panel de tickets")
async def ticket_panel(interaction):
    if not has_permission(interaction):
        return await interaction.response.send_message("❌ Permission refusée. Réservé au staff.", ephemeral=True)
    
    channel = interaction.guild.get_channel(TICKET_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🎫 Support Marauder",
            description="Cliquez sur le bouton ci-dessous pour ouvrir un ticket.\nL'équipe vous répondra rapidement.",
            color=PANEL_COLOR
        )
        embed.set_thumbnail(url=LOGO_URL)
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message(f"✅ Panel de tickets envoyé dans {channel.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Salon de tickets introuvable.", ephemeral=True)

@bot.tree.command(name="reglement", description="Envoyer le règlement")
async def reglement(interaction):
    if not has_owner_role(interaction):
        return await interaction.response.send_message("❌ Permission refusée. Réservé aux administrateurs.", ephemeral=True)
    
    channel = interaction.guild.get_channel(RULES_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="📜 Règlement Marauder",
            description=(
                "En cliquant sur **J'accepte**, tu confirmes avoir lu et accepté les règles.\n\n"
                "**1.** Respecte tous les membres.\n"
                "**2.** Pas de spam ou flood.\n"
                "**3.** Pas de pub sans autorisation.\n"
                "**4.** Marauder est un outil d'investigation. Utilisation responsable uniquement.\n"
                "**5.** Ne partage pas les résultats de recherches publiquement.\n"
                "**6.** Tu es seul responsable de l'utilisation des données.\n"
                "**7.** Tout abus entraîne un ban.\n\n"
                f"✅ **Tu recevras le rôle <@&{MEMBER_ROLE_ID}> après acceptation.**"
            ),
            color=PANEL_COLOR
        )
        embed.set_thumbnail(url=LOGO_URL)
        await channel.send(embed=embed, view=RulesView())
        await interaction.response.send_message(f"✅ Règlement envoyé dans {channel.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Salon de règlement introuvable.", ephemeral=True)

@bot.tree.command(name="add", description="Ajouter une personne au ticket")
async def add_to_ticket(interaction, membre: discord.Member):
    if not has_permission(interaction):
        return await interaction.response.send_message("❌ Permission refusée. Rôle staff requis.", ephemeral=True)
    if not is_ticket_channel(interaction.channel):
        return await interaction.response.send_message("❌ Cette commande n'est utilisable que dans un ticket.", ephemeral=True)
    
    await interaction.channel.set_permissions(membre, read_messages=True, send_messages=True, attach_files=True)
    await interaction.response.send_message(f"✅ {membre.mention} a été ajouté au ticket.")

@bot.tree.command(name="remove", description="Retirer une personne du ticket")
async def remove_from_ticket(interaction, membre: discord.Member):
    if not has_permission(interaction):
        return await interaction.response.send_message("❌ Permission refusée. Rôle staff requis.", ephemeral=True)
    if not is_ticket_channel(interaction.channel):
        return await interaction.response.send_message("❌ Cette commande n'est utilisable que dans un ticket.", ephemeral=True)
    
    await interaction.channel.set_permissions(membre, read_messages=False)
    await interaction.response.send_message(f"✅ {membre.mention} a été retiré du ticket.")

# ============================================
# ÉVÉNEMENTS
# ============================================

@bot.event
async def on_ready():
    for view in [MainView(), TicketView(), CloseTicketView(), RulesView()]:
        bot.add_view(view)
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="/panel | Marauder"))
    print(f"✅ {bot.user} connecté")
    print(f"✅ Salon Ticket: {TICKET_CHANNEL_ID}")
    print(f"✅ Salon Règlement: {RULES_CHANNEL_ID}")
    print(f"✅ Rôle Staff: {STAFF_ROLE_ID}")
    print(f"✅ Rôle Owner: {OWNER_ROLE_ID}")
    print(f"✅ Rôle Membre: {MEMBER_ROLE_ID}")

# ============================================
# LANCEMENT
# ============================================

if __name__ == "__main__":
    bot.run(TOKEN)