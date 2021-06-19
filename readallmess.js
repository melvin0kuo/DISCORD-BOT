const Discord = require('discord.js')
const client = new Discord.Client()
client.on('message', message => {
	console.log(message.content);
});
bot_secret_token = "NjgwMjUwNzIxNzQ0MTkxNDg4.Xk9K2g.CPWSO8Elq9sw6uh0qRDmmYQVgGM"

client.login(bot_secret_token)