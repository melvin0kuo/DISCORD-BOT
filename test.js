const Discord = require('discord.js')
const client = new Discord.Client()

client.on('ready', () => {
    console.log(client.user.tag+ "已連結到伺服器 " )
})
bot_secret_token = "NjgwMjUwNzIxNzQ0MTkxNDg4.XmNEBw.0Sq2PCksGnf5gV9swF8Diik3NvE"

client.login(bot_secret_token)
