const Discord = require('discord.js')
const client = new Discord.Client()
client.on('message', message => {
	console.log(message.content);
});
bot_secret_token = "NjgwMjUwNzIxNzQ0MTkxNDg4.XmNEBw.0Sq2PCksGnf5gV9swF8Diik3NvE"

client.login(bot_secret_token)