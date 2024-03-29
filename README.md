# Neon Chat Bot

## このBOTは何ができるの？
Neon Chat Botは、痒い所に手が届くようなボットです。
ボイスチャットに参加すると、専用のプライベートテキストチャンネルが作成され、ボイスチャットから退出すると、そのテキストチャンネルへのアクセスが解除されます。

### 主な機能
・ボイスチャンネルへの参加/退出時にプライベートテキストチャンネルの作成・テキストの全削除  
・入場時の挨拶メッセージのカスタマイズ  
・スラッシュコマンドを使った挨拶の追加・削除・リスト表示  
・予定した時間にメンション通知を送る

#### コマンド一覧

- `/time_add_comment <time> <comment>`: 指定した時刻とコメントで通知を設定します。リアクションボタンを押すと、指定した時間にメンション通知を送ります。

- `/add_greeting <member> <greeting>`: 特定のメンバーに対するカスタム挨拶メッセージを追加します。メンバーは@メンションまたはユーザーIDで指定できます。

- `/remove_greeting <member> <index>`: 特定のメンバーに対するカスタム挨拶メッセージを削除します。メンバーは@メンションまたはユーザーIDで指定できます。
                                       indexは/list_greetingsで表示される挨拶のリストのインデックス番号です。

- `/list_greetings <member>`: 特定のメンバーに対するカスタム挨拶メッセージのリストを表示します。メンバーは@メンションまたはユーザーIDで指定できます。

##### 使用方法
- 招待リンク
[ここから](https://discord.com/api/oauth2/authorize?client_id=1091866644164395140&permissions=268643376&scope=bot%20applications.commands)

- ***個人で利用したい人***  
1.ボットをDiscordサーバーに招待します。  
2.ボットが必要な権限を持っていることを確認してください。  
3.スラッシュコマンドを使って、挨拶メッセージを追加・削除・リスト表示できます。  

###### ライセンス
このプロジェクトは [MIT License](https://github.com/me846/neon-chat/blob/master/LICENSE) の下でライセンスされています。
