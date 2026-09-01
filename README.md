# 🤖 Marauder Bot

Bot Discord pour la plateforme d'investigation Marauder.

## 📋 Fonctionnalités

- 🔍 **Recherche OSINT** : Recherche multi-critères
- ⚡ **Lookup rapide** : Email, téléphone, IBAN
- 🎫 **Système de tickets** : Support utilisateur
- 📜 **Règlement** : Acceptation avec attribution de rôle

## 🚀 Commandes

| Commande | Description |
|----------|-------------|
| `/panel` | Afficher le panel Marauder |
| `/ticket` | Envoyer le panel de tickets (Staff) |
| `/reglement` | Envoyer le règlement (Owner) |
| `/add` | Ajouter un membre au ticket (Staff) |
| `/remove` | Retirer un membre du ticket (Staff) |

## 🔧 Installation

```bash
# Installer les dépendances
pip install -r requirements.txt

# Configurer .env
cp .env.example .env
# Remplir les tokens

# Lancer le bot
python main.py