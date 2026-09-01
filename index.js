const {
    Client,
    GatewayIntentBits,
    EmbedBuilder,
    ActionRowBuilder,
    ButtonBuilder,
    ButtonStyle,
    ChannelType,
    PermissionFlagsBits,
    SlashCommandBuilder,
    ModalBuilder,
    TextInputBuilder,
    TextInputStyle
} = require('discord.js');
const axios = require('axios');
require('dotenv').config();

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

// ============ LIMITE DES LISTENERS ============
client.setMaxListeners(20);

// ============ COULEURS ============
const COLORS = {
    primary: '#ffffff',
    success: '#00ff88',
    error: '#ff4444',
    warning: '#ffaa00',
    info: '#4488ff'
};

// ============ CONNEXION ============
client.once('ready', () => {
    console.log(`✅ Bot connecté en tant que ${client.user.tag}`);
    client.user.setPresence({
        activities: [{ name: 'Marauder OSINT', type: 3 }],
        status: 'online'
    });
    registerCommands();
});

// ============ COMMANDES ============
async function registerCommands() {
    const commands = [
        new SlashCommandBuilder()
            .setName('panel')
            .setDescription('📊 Afficher le panel Marauder'),

        new SlashCommandBuilder()
            .setName('ticket')
            .setDescription('🎫 Créer un ticket de support'),

        new SlashCommandBuilder()
            .setName('close')
            .setDescription('🔒 Fermer un ticket (Staff uniquement)'),

        new SlashCommandBuilder()
            .setName('add')
            .setDescription('➕ Ajouter un membre au ticket (Staff uniquement)')
            .addUserOption(opt => opt
                .setName('user')
                .setDescription('L\'utilisateur à ajouter')
                .setRequired(true)
            ),

        new SlashCommandBuilder()
            .setName('remove')
            .setDescription('➖ Retirer un membre du ticket (Staff uniquement)')
            .addUserOption(opt => opt
                .setName('user')
                .setDescription('L\'utilisateur à retirer')
                .setRequired(true)
            ),

        new SlashCommandBuilder()
            .setName('recherche')
            .setDescription('🔍 Effectuer une recherche OSINT')
            .addStringOption(opt => opt
                .setName('critere')
                .setDescription('Nom, prénom, email, téléphone...')
                .setRequired(true)
            ),

        new SlashCommandBuilder()
            .setName('lookup')
            .setDescription('📞 Effectuer un lookup')
            .addStringOption(opt => opt
                .setName('type')
                .setDescription('Type de lookup')
                .setRequired(true)
                .addChoices(
                    { name: 'Email', value: 'email' },
                    { name: 'Téléphone', value: 'phone' },
                    { name: 'IBAN', value: 'iban' }
                )
            )
            .addStringOption(opt => opt
                .setName('valeur')
                .setDescription('La valeur à rechercher')
                .setRequired(true)
            )
    ];

    try {
        await client.application.commands.set(commands);
        console.log('✅ Commandes enregistrées');
    } catch (error) {
        console.error('❌ Erreur commandes:', error);
    }
}

// ============ VÉRIFICATION STAFF ============
function isStaff(member) {
    const staffRoleId = process.env.STAFF_ROLE_ID;
    if (!staffRoleId) return false;
    return member.roles.cache.has(staffRoleId);
}

function isTicketChannel(channel) {
    return channel.name && channel.name.startsWith('ticket-');
}

// ============ PANEL ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isChatInputCommand()) return;
    if (interaction.commandName !== 'panel') return;

    const embed = new EmbedBuilder()
        .setTitle('🕵️ Marauder Panel')
        .setDescription('**Bienvenue sur Marauder !**\n\nChoisissez une option ci-dessous pour commencer.')
        .setColor(COLORS.primary)
        .addFields(
            { name: '🔍 Recherche', value: 'Recherche OSINT avancée', inline: true },
            { name: '📞 Lookup', value: 'Lookup email / téléphone / IBAN', inline: true },
            { name: '🎫 Ticket', value: 'Contacter le support', inline: true }
        )
        .setFooter({
            text: 'Marauder • Created by Index',
            iconURL: 'https://cdn.discordapp.com/attachments/1477415267452719208/1543881553220997240/favicon-32x32.png'
        });

    const row = new ActionRowBuilder()
        .addComponents(
            new ButtonBuilder()
                .setCustomId('panel_recherche')
                .setLabel('🔍 Recherche')
                .setStyle(ButtonStyle.Primary),
            new ButtonBuilder()
                .setCustomId('panel_lookup')
                .setLabel('📞 Lookup')
                .setStyle(ButtonStyle.Success),
            new ButtonBuilder()
                .setCustomId('panel_ticket')
                .setLabel('🎫 Ticket')
                .setStyle(ButtonStyle.Secondary),
            new ButtonBuilder()
                .setLabel('🌐 Site Web')
                .setStyle(ButtonStyle.Link)
                .setURL('https://marauder.host')
        );

    await interaction.reply({ embeds: [embed], components: [row] });
});

// ============ TICKET COMMANDE ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isChatInputCommand()) return;
    if (interaction.commandName !== 'ticket') return;

    const modal = new ModalBuilder()
        .setCustomId('ticket_modal')
        .setTitle('🎫 Créer un ticket');

    const subjectInput = new TextInputBuilder()
        .setCustomId('ticket_subject')
        .setLabel('📌 Sujet du ticket')
        .setPlaceholder('Ex: Problème de connexion')
        .setStyle(TextInputStyle.Short)
        .setRequired(true)
        .setMaxLength(100);

    const descInput = new TextInputBuilder()
        .setCustomId('ticket_description')
        .setLabel('📝 Description du problème')
        .setPlaceholder('Décrivez votre problème en détail...')
        .setStyle(TextInputStyle.Paragraph)
        .setRequired(true)
        .setMaxLength(1000);

    modal.addComponents(
        new ActionRowBuilder().addComponents(subjectInput),
        new ActionRowBuilder().addComponents(descInput)
    );

    await interaction.showModal(modal);
});

// ============ BOUTON TICKET DU PANEL ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isButton()) return;
    if (interaction.customId !== 'panel_ticket') return;

    const modal = new ModalBuilder()
        .setCustomId('ticket_modal')
        .setTitle('🎫 Créer un ticket');

    const subjectInput = new TextInputBuilder()
        .setCustomId('ticket_subject')
        .setLabel('📌 Sujet du ticket')
        .setPlaceholder('Ex: Problème de connexion')
        .setStyle(TextInputStyle.Short)
        .setRequired(true)
        .setMaxLength(100);

    const descInput = new TextInputBuilder()
        .setCustomId('ticket_description')
        .setLabel('📝 Description du problème')
        .setPlaceholder('Décrivez votre problème en détail...')
        .setStyle(TextInputStyle.Paragraph)
        .setRequired(true)
        .setMaxLength(1000);

    modal.addComponents(
        new ActionRowBuilder().addComponents(subjectInput),
        new ActionRowBuilder().addComponents(descInput)
    );

    await interaction.showModal(modal);
});

// ============ SOUMISSION DU TICKET ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isModalSubmit()) return;
    if (interaction.customId !== 'ticket_modal') return;

    const subject = interaction.fields.getTextInputValue('ticket_subject');
    const description = interaction.fields.getTextInputValue('ticket_description');

    await interaction.deferReply({ ephemeral: true });

    try {
        const guild = interaction.guild;

        let category = guild.channels.cache.find(c => c.name === '🎫 Tickets' && c.type === ChannelType.GuildCategory);
        if (!category) {
            category = await guild.channels.create({
                name: '🎫 Tickets',
                type: ChannelType.GuildCategory,
                permissionOverwrites: [{
                    id: guild.id,
                    deny: [PermissionFlagsBits.ViewChannel]
                }, {
                    id: process.env.STAFF_ROLE_ID,
                    allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages]
                }]
            });
        }

        const ticketChannel = await guild.channels.create({
            name: `ticket-${interaction.user.username}`,
            type: ChannelType.GuildText,
            parent: category.id,
            permissionOverwrites: [{
                id: guild.id,
                deny: [PermissionFlagsBits.ViewChannel]
            }, {
                id: interaction.user.id,
                allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages, PermissionFlagsBits.ReadMessageHistory]
            }, {
                id: process.env.STAFF_ROLE_ID,
                allow: [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.SendMessages, PermissionFlagsBits.ReadMessageHistory, PermissionFlagsBits.ManageChannels]
            }]
        });

        const embed = new EmbedBuilder()
            .setTitle(`🎫 Ticket : ${subject}`)
            .setDescription(description)
            .setColor(COLORS.primary)
            .addFields({ name: '👤 Créé par', value: interaction.user.tag, inline: true },
                { name: '📅 Date', value: new Date().toLocaleString(), inline: true },
                { name: '📌 Statut', value: '🟢 Ouvert', inline: true }
            )
            .setFooter({ text: 'Marauder Support' });

        const row = new ActionRowBuilder()
            .addComponents(
                new ButtonBuilder()
                    .setCustomId('ticket_close')
                    .setLabel('🔒 Fermer')
                    .setStyle(ButtonStyle.Danger),
                new ButtonBuilder()
                    .setCustomId('ticket_add')
                    .setLabel('➕ Ajouter')
                    .setStyle(ButtonStyle.Success)
            );

        await ticketChannel.send({
            content: `<@${interaction.user.id}> <@&${process.env.STAFF_ROLE_ID}>`,
            embeds: [embed],
            components: [row]
        });

        await interaction.editReply({
            content: `✅ Votre ticket a été créé ! ➡️ ${ticketChannel}`
        });

    } catch (error) {
        console.error('Erreur création ticket:', error);
        await interaction.editReply({
            content: '❌ Erreur lors de la création du ticket.'
        });
    }
});

// ============ FERMER UN TICKET (BOUTON) ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isButton()) return;
    if (interaction.customId !== 'ticket_close') return;

    const channel = interaction.channel;

    if (!isTicketChannel(channel)) {
        return interaction.reply({
            content: '❌ Cette commande ne peut être utilisée que dans un ticket.',
            ephemeral: true
        });
    }

    if (!isStaff(interaction.member)) {
        return interaction.reply({
            content: '❌ Seul le staff peut fermer un ticket.',
            ephemeral: true
        });
    }

    await interaction.reply({
        content: '🔒 Ce ticket va être fermé dans 5 secondes...'
    });

    setTimeout(async () => {
        await channel.delete();
    }, 5000);
});

// ============ COMMANDE /CLOSE ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isChatInputCommand()) return;
    if (interaction.commandName !== 'close') return;

    const channel = interaction.channel;

    if (!isTicketChannel(channel)) {
        return interaction.reply({
            content: '❌ Cette commande ne peut être utilisée que dans un ticket.',
            ephemeral: true
        });
    }

    if (!isStaff(interaction.member)) {
        return interaction.reply({
            content: '❌ Seul le staff peut fermer un ticket.',
            ephemeral: true
        });
    }

    await interaction.reply({
        content: '🔒 Ce ticket va être fermé dans 5 secondes...'
    });

    setTimeout(async () => {
        await channel.delete();
    }, 5000);
});

// ============ AJOUTER UN MEMBRE (BOUTON) ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isButton()) return;
    if (interaction.customId !== 'ticket_add') return;

    if (!isTicketChannel(interaction.channel)) {
        return interaction.reply({
            content: '❌ Cette commande ne peut être utilisée que dans un ticket.',
            ephemeral: true
        });
    }

    if (!isStaff(interaction.member)) {
        return interaction.reply({
            content: '❌ Seul le staff peut ajouter des membres.',
            ephemeral: true
        });
    }

    const modal = new ModalBuilder()
        .setCustomId('ticket_add_modal')
        .setTitle('➕ Ajouter un membre');

    const userInput = new TextInputBuilder()
        .setCustomId('ticket_add_user')
        .setLabel('ID ou @mention de l\'utilisateur')
        .setPlaceholder('Ex: @utilisateur ou 123456789')
        .setStyle(TextInputStyle.Short)
        .setRequired(true);

    modal.addComponents(
        new ActionRowBuilder().addComponents(userInput)
    );

    await interaction.showModal(modal);
});

// ============ MODAL AJOUTER ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isModalSubmit()) return;
    if (interaction.customId !== 'ticket_add_modal') return;

    const input = interaction.fields.getTextInputValue('ticket_add_user');
    const userId = input.replace(/[<@!>]/g, '');

    try {
        const user = await interaction.client.users.fetch(userId);

        await interaction.channel.permissionOverwrites.edit(userId, {
            ViewChannel: true,
            SendMessages: true,
            ReadMessageHistory: true
        });

        await interaction.reply({
            content: `✅ ${user.tag} a été ajouté au ticket.`
        });

    } catch (error) {
        await interaction.reply({
            content: '❌ Utilisateur introuvable. Vérifiez l\'ID ou la mention.',
            ephemeral: true
        });
    }
});

// ============ COMMANDE /ADD ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isChatInputCommand()) return;
    if (interaction.commandName !== 'add') return;

    const user = interaction.options.getUser('user');

    if (!isTicketChannel(interaction.channel)) {
        return interaction.reply({
            content: '❌ Cette commande ne peut être utilisée que dans un ticket.',
            ephemeral: true
        });
    }

    if (!isStaff(interaction.member)) {
        return interaction.reply({
            content: '❌ Seul le staff peut ajouter des membres.',
            ephemeral: true
        });
    }

    try {
        await interaction.channel.permissionOverwrites.edit(user.id, {
            ViewChannel: true,
            SendMessages: true,
            ReadMessageHistory: true
        });

        await interaction.reply({
            content: `✅ ${user.tag} a été ajouté au ticket.`
        });

    } catch (error) {
        await interaction.reply({
            content: '❌ Erreur lors de l\'ajout.',
            ephemeral: true
        });
    }
});

// ============ COMMANDE /REMOVE ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isChatInputCommand()) return;
    if (interaction.commandName !== 'remove') return;

    const user = interaction.options.getUser('user');

    if (!isTicketChannel(interaction.channel)) {
        return interaction.reply({
            content: '❌ Cette commande ne peut être utilisée que dans un ticket.',
            ephemeral: true
        });
    }

    if (!isStaff(interaction.member)) {
        return interaction.reply({
            content: '❌ Seul le staff peut retirer des membres.',
            ephemeral: true
        });
    }

    if (user.id === interaction.user.id) {
        return interaction.reply({
            content: '❌ Vous ne pouvez pas vous retirer vous-même.',
            ephemeral: true
        });
    }

    try {
        await interaction.channel.permissionOverwrites.delete(user.id);

        await interaction.reply({
            content: `✅ ${user.tag} a été retiré du ticket.`
        });

    } catch (error) {
        await interaction.reply({
            content: '❌ Erreur lors du retrait.',
            ephemeral: true
        });
    }
});

// ============ BOUTON RECHERCHE DU PANEL ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isButton()) return;
    if (interaction.customId !== 'panel_recherche') return;

    const modal = new ModalBuilder()
        .setCustomId('recherche_modal')
        .setTitle('🔍 Recherche OSINT');

    const input = new TextInputBuilder()
        .setCustomId('recherche_input')
        .setLabel('Critère de recherche')
        .setPlaceholder('Nom, prénom, email, téléphone, IP...')
        .setStyle(TextInputStyle.Short)
        .setRequired(true);

    modal.addComponents(new ActionRowBuilder().addComponents(input));
    await interaction.showModal(modal);
});

// ============ BOUTON LOOKUP DU PANEL ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isButton()) return;
    if (interaction.customId !== 'panel_lookup') return;

    const modal = new ModalBuilder()
        .setCustomId('lookup_modal')
        .setTitle('📞 Lookup');

    const typeInput = new TextInputBuilder()
        .setCustomId('lookup_type')
        .setLabel('Type (email, phone, iban)')
        .setPlaceholder('email / phone / iban')
        .setStyle(TextInputStyle.Short)
        .setRequired(true);

    const valueInput = new TextInputBuilder()
        .setCustomId('lookup_value')
        .setLabel('Valeur')
        .setPlaceholder('jean.dupont@gmail.com')
        .setStyle(TextInputStyle.Short)
        .setRequired(true);

    modal.addComponents(
        new ActionRowBuilder().addComponents(typeInput),
        new ActionRowBuilder().addComponents(valueInput)
    );
    await interaction.showModal(modal);
});

// ============ MODAL RECHERCHE ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isModalSubmit()) return;
    if (interaction.customId !== 'recherche_modal') return;

    const critere = interaction.fields.getTextInputValue('recherche_input');

    await interaction.reply({
        content: `⏳ Recherche en cours pour : **${critere}**...`,
        ephemeral: true
    });

    try {
        const response = await axios.post('https://api.brixhub.to/api/v1/search', {
            flexible: true,
            per_page: 5,
            query: critere
        }, {
            headers: { 'X-API-Key': process.env.BRIX_API_KEY }
        });

        const results = response.data.data?.results || [];

        if (results.length === 0) {
            return interaction.editReply({
                content: `❌ Aucun résultat trouvé pour : **${critere}**`
            });
        }

        const embed = new EmbedBuilder()
            .setTitle(`🔍 Résultats pour : ${critere}`)
            .setColor(COLORS.primary)
            .setFooter({ text: `Marauder Lookup • ${results.length} résultat(s)` });

        results.slice(0, 5).forEach((person, i) => {
            const name = `${person.prenom || ''} ${person.nom_famille || 'Inconnu'}`.trim();
            const info = [];
            if (person.email) info.push(`📧 ${person.email}`);
            if (person.telephone) info.push(`📱 ${person.telephone}`);
            if (person.adresse) info.push(`📍 ${person.adresse}`);
            if (person.ville) info.push(`🏙️ ${person.ville}`);

            embed.addFields({
                name: `${i+1}. ${name}`,
                value: info.join('\n') || 'Aucune information détaillée',
                inline: false
            });
        });

        await interaction.editReply({
            content: null,
            embeds: [embed]
        });

    } catch (error) {
        console.error('Erreur recherche:', error);
        await interaction.editReply({
            content: '❌ Erreur lors de la recherche.'
        });
    }
});

// ============ MODAL LOOKUP ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isModalSubmit()) return;
    if (interaction.customId !== 'lookup_modal') return;

    const type = interaction.fields.getTextInputValue('lookup_type').toLowerCase();
    const value = interaction.fields.getTextInputValue('lookup_value');

    if (!['email', 'phone', 'iban'].includes(type)) {
        return interaction.reply({
            content: '❌ Type invalide. Utilisez : email, phone ou iban',
            ephemeral: true
        });
    }

    await interaction.reply({
        content: `⏳ Lookup en cours pour : **${value}** (${type})...`,
        ephemeral: true
    });

    try {
        const response = await axios.get(
            `https://api.brixhub.to/api/v1/lookup/${type}/${encodeURIComponent(value)}`, {
                headers: { 'X-API-Key': process.env.BRIX_API_KEY }
            }
        );

        const results = response.data.data?.results || [];

        if (results.length === 0) {
            return interaction.editReply({
                content: `❌ Aucun résultat trouvé pour : **${value}**`
            });
        }

        const embed = new EmbedBuilder()
            .setTitle(`📞 Lookup ${type} : ${value}`)
            .setColor(COLORS.primary)
            .setFooter({ text: `Marauder Lookup • ${results.length} résultat(s)` });

        results.slice(0, 5).forEach((row, i) => {
            const info = Object.entries(row)
                .filter(([k]) => !k.startsWith('_'))
                .map(([k, v]) => `${k}: ${v}`)
                .join('\n');

            embed.addFields({
                name: `📋 Enregistrement ${i+1}`,
                value: info || 'Aucune information',
                inline: false
            });
        });

        await interaction.editReply({
            content: null,
            embeds: [embed]
        });

    } catch (error) {
        console.error('Erreur lookup:', error);
        await interaction.editReply({
            content: '❌ Erreur lors du lookup.'
        });
    }
});

// ============ COMMANDE /RECHERCHE ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isChatInputCommand()) return;
    if (interaction.commandName !== 'recherche') return;

    const critere = interaction.options.getString('critere');

    await interaction.reply({
        content: `⏳ Recherche en cours pour : **${critere}**...`,
        ephemeral: true
    });

    try {
        const response = await axios.post('https://api.brixhub.to/api/v1/search', {
            flexible: true,
            per_page: 5,
            query: critere
        }, {
            headers: { 'X-API-Key': process.env.BRIX_API_KEY }
        });

        const results = response.data.data?.results || [];

        if (results.length === 0) {
            return interaction.editReply({
                content: `❌ Aucun résultat trouvé pour : **${critere}**`
            });
        }

        const embed = new EmbedBuilder()
            .setTitle(`🔍 Résultats pour : ${critere}`)
            .setColor(COLORS.primary)
            .setFooter({ text: `Marauder Lookup • ${results.length} résultat(s)` });

        results.slice(0, 5).forEach((person, i) => {
            const name = `${person.prenom || ''} ${person.nom_famille || 'Inconnu'}`.trim();
            const info = [];
            if (person.email) info.push(`📧 ${person.email}`);
            if (person.telephone) info.push(`📱 ${person.telephone}`);
            if (person.adresse) info.push(`📍 ${person.adresse}`);
            if (person.ville) info.push(`🏙️ ${person.ville}`);

            embed.addFields({
                name: `${i+1}. ${name}`,
                value: info.join('\n') || 'Aucune information détaillée',
                inline: false
            });
        });

        await interaction.editReply({
            content: null,
            embeds: [embed]
        });

    } catch (error) {
        console.error('Erreur recherche:', error);
        await interaction.editReply({
            content: '❌ Erreur lors de la recherche.'
        });
    }
});

// ============ COMMANDE /LOOKUP ============
client.on('interactionCreate', async (interaction) => {
    if (!interaction.isChatInputCommand()) return;
    if (interaction.commandName !== 'lookup') return;

    const type = interaction.options.getString('type');
    const value = interaction.options.getString('valeur');

    await interaction.reply({
        content: `⏳ Lookup en cours pour : **${value}** (${type})...`,
        ephemeral: true
    });

    try {
        const response = await axios.get(
            `https://api.brixhub.to/api/v1/lookup/${type}/${encodeURIComponent(value)}`, {
                headers: { 'X-API-Key': process.env.BRIX_API_KEY }
            }
        );

        const results = response.data.data?.results || [];

        if (results.length === 0) {
            return interaction.editReply({
                content: `❌ Aucun résultat trouvé pour : **${value}**`
            });
        }

        const embed = new EmbedBuilder()
            .setTitle(`📞 Lookup ${type} : ${value}`)
            .setColor(COLORS.primary)
            .setFooter({ text: `Marauder Lookup • ${results.length} résultat(s)` });

        results.slice(0, 5).forEach((row, i) => {
            const info = Object.entries(row)
                .filter(([k]) => !k.startsWith('_'))
                .map(([k, v]) => `${k}: ${v}`)
                .join('\n');

            embed.addFields({
                name: `📋 Enregistrement ${i+1}`,
                value: info || 'Aucune information',
                inline: false
            });
        });

        await interaction.editReply({
            content: null,
            embeds: [embed]
        });

    } catch (error) {
        console.error('Erreur lookup:', error);
        await interaction.editReply({
            content: '❌ Erreur lors du lookup.'
        });
    }
});

// ============ DÉMARRAGE ============
client.login(process.env.DISCORD_TOKEN);
console.log('🚀 Marauder Bot démarré');