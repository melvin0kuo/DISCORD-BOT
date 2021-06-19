const Discord = require('Discord.js')
const client = new Discord.Client()

client.on('message', message => {
//讀取訊息，並回覆
if (message.content === '下午好') {
	message.channel.send('下午好啊！owo');
}
if (message.content === '晚上好') {
	message.channel.send('晚安.');
}
if (message.content === '早安'){
    message.channel.send('早上好啊！！');}
//以上可增加回覆條件
});

bot_secret_token ="NjgwMjUwNzIxNzQ0MTkxNDg4.Xk9K2g.CPWSO8Elq9sw6uh0qRDmmYQVgGM"
client.login(bot_secret_token)