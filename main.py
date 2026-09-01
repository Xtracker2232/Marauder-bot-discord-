import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import aiohttp
import io
from datetime import datetime
import os
from dotenv import load_dotenv
import asyncio

# ============================================
# CHARGER LES VARIABLES D'ENVIRONNEMENT
# ============================================
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
BRIX_KEY = os.getenv('BRIX_KEY')
API_URL = os.getenv('API_URL', "https://marauder.host")
BRIX_API_URL = os.getenv('BRIX_API_URL', "https://api.brixhub.to/api/v1")

if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN non défini !")
if not BRIX_KEY:
    raise ValueError("❌ BRIX_KEY non défini !")

# ============================================
# CONFIGURATION AVEC TES ID
# ============================================
MAX_RESULTS = 10
PANEL_COLOR = 0x6366f1
LOGO_URL = "https://cdn.discordapp.com/attachments/1477415267452719208/1543881553220997240/favicon-32x32.png?ex=6a967b3e&is=6a9529be&hm=73725b0a8477c3d60cad60b87ea9d91bfbb90672f606b199b78e5e797d1cdb7b&"

# ============================================
# ID QUE TU M'AS DONNÉ
# ============================================
TICKET_CHANNEL_ID = 1544288399781797930     # Salon ticket
RULES_CHANNEL_ID = 1544282830039810168      # Salon règlement
STAFF_ROLE_ID = 1544289961942065172         # Rôle staff (add/remove)
OWNER_ROLE_ID = 1544301570588672042         # Rôle owner (toutes commandes)
MEMBER_ROLE_ID = 1544282221916065792        # Rôle membre (attribué après acceptation règles)

# ============================================
# INTENTS
# ============================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ============================================
# STATS
# ============================================
bot_stats = {"searches": 0, "users": set()}

# ============================================
# FONCTIONS DE VÉRIFICATION DES RÔLES
# ============================================

def has_owner_role(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    role = interaction.guild.get_role(OWNER_ROLE_ID)
    if not role:
        return False
    return role in interaction.user.roles

def has_staff_role(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    role = interaction.guild.get_role(STAFF_ROLE_ID)
    if not role:
        return False
    return role in interaction.user.roles

def has_permission(interaction: discord.Interaction) -> bool:
    return has_staff_role(interaction) or has_owner_role(interaction)

def is_ticket_channel(channel) -> bool:
    return channel.name.startswith("ticket-")

# ============================================
# FONCTIONS UTILITAIRES
# ============================================

def use_search(uid):
    bot_stats["searches"] += 1
    bot_stats["users"].add(uid)

# ============================================
# API BRIX
# ============================================

async def brix_search(payload):
    headers = {
        "X-API-Key": BRIX_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Marauder-Bot/1.0"
    }
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
    e = discord.Embed(
        title=f"👤 {name}",
        description="\n".join(lines) or "Aucune donnée disponible",
        color=PANEL_COLOR
    )
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
        
        self.add_item(Button(
            label="🌐 Site Web",
            style=discord.ButtonStyle.link,
            url="https://marauder.host"
        ))
        
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.index <= 0
        self.next_btn.disabled = self.index >= len(self.results) - 1
        self.counter_btn.label = f"{self.index + 1} / {len(self.results)}"

    def current_embed(self):
        return format_profile(self.results[self.index], self.index, len(self.results))

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="prev_btn")
    async def prev_btn(self, interaction: discord.Interaction, button: Button):
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.secondary, disabled=True, custom_id="counter_btn")
    async def counter_btn(self, interaction: discord.Interaction, button: Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, custom_id="next_btn")
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="📥 Télécharger .txt", style=discord.ButtonStyle.success, custom_id="download_btn")
    async def download_btn(self, interaction: discord.Interaction, button: Button):
        txt = results_to_txt(self.results, self.query_info)
        f = discord.File(io.BytesIO(txt.encode("utf-8")), filename="marauder_resultats.txt")
        await interaction.response.send_message(
            content="📥 Voici vos résultats en `.txt` :",
            file=f,
            ephemeral=True
        )

    @discord.ui.button(label="❌ Fermer", style=discord.ButtonStyle.danger, custom_id="close_btn")
    async def close_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="✅ Résultats fermés", color=0x22c55e),
            view=None
        )

# ============================================
# MODALS
# ============================================

class SearchModal(Modal, title="🔍 Recherche Marauder"):
    nom = TextInput(label="Nom de famille", placeholder="Dupont", required=False)
    prenom = TextInput(label="Prénom", placeholder="Jean", required=False)
    email = TextInput(label="Email", placeholder="jean@gmail.com", required=False)
    telephone = TextInput(label="Téléphone", placeholder="0612345678", required=False)
    ville = TextInput(label="Ville", placeholder="Paris", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid = interaction.user.id
        
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
            e = discord.Embed(title="❌ Champs vides", description="Remplissez au moins un champ.", color=0xef4444)
            await interaction.followup.send(embed=e, ephemeral=True)
            return
        
        loading_embed = discord.Embed(
            title="⏳ Marauder Lookup",
            description="**Recherche en cours...**\nVeuillez patienter pendant que nous analysons les données.",
            color=PANEL_COLOR
        )
        loading_embed.set_footer(text="Marauder · Recherche en cours")
        loading_message = await interaction.followup.send(embed=loading_embed, ephemeral=True)
        
        status, data = await brix_search(payload)
        
        if status != 200:
            e = discord.Embed(title="❌ Erreur API", description=f"Code {status} — réessayez.", color=0xef4444)
            await loading_message.edit(embed=e, view=None)
            return
        
        results = data.get("data", {}).get("results", [])
        total = data.get("meta", {}).get("total", 0)
        took = data.get("meta", {}).get("took_ms", 0)
        
        use_search(uid)
        
        if not results:
            e = discord.Embed(title="😶 Aucun résultat", description="Essayez avec moins de critères.", color=0xf59e0b)
            await loading_message.edit(embed=e, view=None)
            return
        
        query_info = " · ".join(query_parts)
        view = ResultsView(results, total, took, query_info, loading_message)
        
        header = discord.Embed(
            title=f"🔍 {total:,} résultat{'s' if total > 1 else ''} · {took}ms",
            description=f"Affichage de **{min(len(results), MAX_RESULTS)}** fiches",
            color=PANEL_COLOR
        )
        
        await loading_message.delete()
        await interaction.followup.send(embed=header, ephemeral=True)
        await interaction.followup.send(embed=view.current_embed(), view=view, ephemeral=True)

class LookupModal(Modal, title="⚡ Lookup rapide"):
    value = TextInput(label="Email, téléphone ou IBAN", placeholder="jean@gmail.com / 0612345678 / FR76...")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid = interaction.user.id
        
        loading_embed = discord.Embed(
            title="⏳ Marauder Lookup",
            description="**Recherche en cours...**",
            color=PANEL_COLOR
        )
        loading_embed.set_footer(text="Marauder · Recherche en cours")
        loading_message = await interaction.followup.send(embed=loading_embed, ephemeral=True)
        
        status, data = await brix_lookup(str(self.value).strip())
        
        if status != 200:
            e = discord.Embed(title="❌ Erreur API", description=f"Code {status} — réessayez.", color=0xef4444)
            await loading_message.edit(embed=e, view=None)
            return
        
        results = data.get("data", {}).get("results", [])
        total = data.get("meta", {}).get("total", 0)
        took = data.get("meta", {}).get("took_ms", 0)
        
        use_search(uid)
        
        if not results:
            e = discord.Embed(title="😶 Aucun résultat", color=0xf59e0b)
            await loading_message.edit(embed=e, view=None)
            return
        
        query_info = str(self.value).strip()
        view = ResultsView(results, total, took, query_info, loading_message)
        
        header = discord.Embed(
            title=f"⚡ {total:,} résultat{'s' if total > 1 else ''} · {took}ms",
            description=f"Affichage de **{min(len(results), MAX_RESULTS)}** fiches",
            color=PANEL_COLOR
        )
        
        await loading_message.delete()
        await interaction.followup.send(embed=header, ephemeral=True)
        await interaction.followup.send(embed=view.current_embed(), view=view, ephemeral=True)

# ============================================
# MAIN VIEW (PERSISTANTE)
# ============================================

class MainView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(
            label="🌐 Site Web",
            style=discord.ButtonStyle.link,
            url="https://marauder.host",
            row=1
        ))

    @discord.ui.button(label="🔍 Rechercher", style=discord.ButtonStyle.primary, custom_id="main_search", row=0)
    async def search(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SearchModal())

    @discord.ui.button(label="⚡ Lookup rapide", style=discord.ButtonStyle.secondary, custom_id="main_lookup", row=0)
    async def lookup(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(LookupModal())

# ============================================
# TICKET SYSTEM
# ============================================

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        
        existing = discord.utils.get(guild.channels, name=f"ticket-{interaction.user.name.lower()}")
        if existing:
            await interaction.response.send_message(f"❌ Vous avez déjà un ticket ouvert : {existing.mention}", ephemeral=True)
            return
        
        ticket_channel = guild.get_channel(TICKET_CHANNEL_ID)
        if not ticket_channel:
            await interaction.response.send_message("❌ Salon de tickets introuvable.", ephemeral=True)
            return
        
        category = ticket_channel.category
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        staff_role = guild.get_role(STAFF_ROLE_ID)
        owner_role = guild.get_role(OWNER_ROLE_ID)
        
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if owner_role:
            overwrites[owner_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name.lower()}",
            category=category,
            overwrites=overwrites,
            topic=f"Ticket de {interaction.user} | ID: {interaction.user.id}"
        )
        
        ticket_embed = discord.Embed(
            title="🎫 Ticket ouvert",
            description=(
                f"Bienvenue {interaction.user.mention} !\n\n"
                "Expliquez votre problème ou votre demande, un membre de l'équipe vous répondra rapidement."
            ),
            color=PANEL_COLOR
        )
        ticket_embed.set_thumbnail(url=LOGO_URL)
        ticket_embed.set_footer(text="Marauder Support · Cliquez sur Fermer pour clôturer le ticket")
        
        await channel.send(embed=ticket_embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Votre ticket a été créé : {channel.mention}", ephemeral=True)

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        if not has_permission(interaction):
            await interaction.response.send_message("❌ Vous n'avez pas la permission de fermer ce ticket.", ephemeral=True)
            return
        
        channel = interaction.channel
        
        embed = discord.Embed(
            title="🔒 Ticket fermé",
            description=f"Fermé par {interaction.user.mention}. Suppression dans 5 secondes.",
            color=0xef4444
        )
        embed.set_thumbnail(url=LOGO_URL)
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        
        try:
            await channel.delete(reason="Ticket fermé")
        except Exception as ex:
            print(f"Erreur suppression salon: {ex}")

# ============================================
# RÈGLEMENT AVEC ATTRIBUTION DU RÔLE MEMBRE
# ============================================

class RulesView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ J'accepte le règlement", style=discord.ButtonStyle.success, custom_id="accept_rules")
    async def accept_rules(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        
        # Récupérer le rôle membre
        role = guild.get_role(MEMBER_ROLE_ID)
        
        if not role:
            await interaction.response.send_message("❌ Rôle membre introuvable. Contactez un administrateur.", ephemeral=True)
            return
        
        # Vérifier si l'utilisateur a déjà le rôle
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ Tu as déjà accepté le règlement !", ephemeral=True)
            return
        
        try:
            # Ajouter le rôle
            await interaction.user.add_roles(role, reason="Règlement accepté")
            
            embed = discord.Embed(
                title="✅ Règlement accepté !",
                description=f"Tu as accepté le règlement et obtenu le rôle **{role.name}** !\n\nBienvenue sur Marauder ! 🚀",
                color=0x22c55e
            )
            embed.set_thumbnail(url=LOGO_URL)
            embed.set_footer(text="Marauder • Bonne investigation !")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Je n'ai pas la permission d'attribuer ce rôle. Contacte un administrateur.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Erreur lors de l'attribution du rôle : {e}",
                ephemeral=True
            )

# ============================================
# COMMANDES DE TICKET (STAFF ET OWNER)
# ============================================

@bot.tree.command(name="add", description="Ajouter une personne au ticket")
async def add_to_ticket(interaction: discord.Interaction, membre: discord.Member):
    if not has_permission(interaction):
        await interaction.response.send_message("❌ Permission refusée. Rôle staff requis.", ephemeral=True)
        return
    
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message("❌ Cette commande n'est utilisable que dans un ticket.", ephemeral=True)
        return
    
    try:
        await interaction.channel.set_permissions(membre, read_messages=True, send_messages=True, attach_files=True)
        await interaction.response.send_message(f"✅ {membre.mention} a été ajouté au ticket.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

@bot.tree.command(name="remove", description="Retirer une personne du ticket")
async def remove_from_ticket(interaction: discord.Interaction, membre: discord.Member):
    if not has_permission(interaction):
        await interaction.response.send_message("❌ Permission refusée. Rôle staff requis.", ephemeral=True)
        return
    
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message("❌ Cette commande n'est utilisable que dans un ticket.", ephemeral=True)
        return
    
    try:
        await interaction.channel.set_permissions(membre, read_messages=False)
        await interaction.response.send_message(f"✅ {membre.mention} a été retiré du ticket.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

# ============================================
# COMMANDES SLASH
# ============================================

@bot.tree.command(name="panel", description="Afficher le panel Marauder")
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="**Marauder Lookup**",
        color=PANEL_COLOR
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1477415267452719208/1529531032720904202/image.png?ex=6a906ac7&is=6a8f1947&hm=500ceaaff4f42681d8b101ce1a2e8c40591a7ac7b96ae3ed5e6a358f503d65ae&")
    embed.set_footer(text="Created by Index")
    await interaction.response.send_message(embed=embed, view=MainView())

@bot.tree.command(name="ticket", description="Envoyer le panel de tickets")
async def ticket_panel(interaction: discord.Interaction):
    if not has_permission(interaction):
        await interaction.response.send_message("❌ Permission refusée. Réservé au staff.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🎫 Support Marauder",
        description="**Besoin d'aide ?**\n\nCliquez sur le bouton ci-dessous pour ouvrir un ticket.\nL'équipe vous répondra rapidement.",
        color=PANEL_COLOR
    )
    embed.set_thumbnail(url=LOGO_URL)
    embed.set_footer(text="Marauder Support")
    
    channel = interaction.guild.get_channel(TICKET_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message(f"✅ Panel de tickets envoyé dans {channel.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Salon de tickets introuvable.", ephemeral=True)

@bot.tree.command(name="reglement", description="Afficher le règlement avec bouton d'acceptation")
async def reglement(interaction: discord.Interaction):
    if not has_owner_role(interaction):
        await interaction.response.send_message("❌ Permission refusée. Réservé aux administrateurs.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📜 Règlement — Marauder",
        description=(
            "En cliquant sur **J'accepte**, tu confirmes avoir lu et accepté les règles suivantes.\n\n"
            "**1.** Respecte tous les membres. Aucune insulte tolérée.\n"
            "**2.** Pas de spam ou flood dans les salons.\n"
            "**3.** Pas de pub sans autorisation d'un admin.\n"
            "**4.** Marauder est un outil d'investigation. Interdiction de l'utiliser pour harcèlement ou menaces.\n"
            "**5.** Ne partage pas les résultats de recherches publiquement dans les salons.\n"
            "**6.** Tu es seul responsable de l'utilisation des données trouvées.\n"
            "**7.** Tout abus entraîne un ban immédiat du site et du Discord.\n"
            "**8.** Ne partage jamais tes identifiants de connexion.\n"
            "**9.** Les admins peuvent sanctionner tout comportement inapproprié.\n\n"
            "En acceptant ce règlement, tu acceptes nos CGU disponibles sur [marauder.host](https://marauder.host/cgu.html).\n\n"
            f"✅ **Tu recevras le rôle <@&{MEMBER_ROLE_ID}> après acceptation.**"
        ),
        color=PANEL_COLOR
    )
    embed.set_thumbnail(url=LOGO_URL)
    embed.set_footer(text="Marauder · Cliquez sur le bouton pour accepter")
    
    channel = interaction.guild.get_channel(RULES_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=RulesView())
        await interaction.response.send_message(f"✅ Règlement envoyé dans {channel.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Salon de règlement introuvable.", ephemeral=True)

# ============================================
# ÉVÉNEMENTS
# ============================================

@bot.event
async def on_ready():
    bot.add_view(MainView())
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    bot.add_view(RulesView())
    
    await bot.tree.sync()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name="/panel | Marauder")
    )
    print(f"✅ {bot.user} connecté sur {len(bot.guilds)} serveur(s)")
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