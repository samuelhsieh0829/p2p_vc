# P2P Voice Chat
## 簡介
這個程式透過P2P(Point to Point)，建立使用者之間的連線，語音封包不經過伺服器端，讓語音通話可以享有更低的延遲
## 客戶端說明
客戶端程式有兩種可以使用
### 1.使用發行版本
- 到這邊下載[client.zip](https://github.com/samuelhsieh0829/p2p_vc/releases/download/0.1/client.zip)並將其解壓縮
- 進入`client`目錄，打開`client.exe`即可
### 2.運行原始碼
- 先到[Python官網](https://www.python.org/downloads/)下載Python 3.11.7版本的安裝檔(其他版本理論上也可以，但沒測試過)
- 開啟安裝檔，**勾選`Add Python 3.x to PATH`**，然後一直按下一步，直到安裝好
- 下載[Source Code](https://github.com/samuelhsieh0829/p2p_vc/archive/refs/tags/0.1.zip)並解壓縮(或是使用git clone https://github.com/samuelhsieh0829/p2p_vc.git)
- 進入`p2p-vc`目錄，開啟cmd，執行`pip install -r requirements.txt`以安裝依賴模組
- 進入`client_code`目錄，執行`client.py`

## 客戶端內操作說明
- 第一次開啟時，可以輸入使用者名稱，輸入後會儲存到`_internal/config.json`中，之後開啟會自動載入內部設定
- 輸入頻道ID(從 https://vc.itzowo.net/channels 取得)
- 目前僅有exit指令可以使用，用於關閉程式
- 亦可透過按下鍵盤`Ctrl+C`結束程式

## 伺服器端架設
- 先安裝Python、下載[原始碼](https://github.com/samuelhsieh0829/p2p_vc/archive/refs/tags/0.1.zip)並安裝依賴模組(步驟與上述運行原始碼相同)
- 進入`server_code`目錄，執行`server.py`

## API、ENDPOINT
### GET
- `/` 首頁
- `/channels` 顯示所有頻道、新增頻道
- `/channels/create` 建立頻道，須包含參數name、description、author，可選填channel_id
- `/channels/delete/<int:channel_id>` 刪除頻道

### POST
- `/api/channels` 取得所有頻道資訊
- `/api/channels/create` 建立頻道，須包含參數name、description、author，可選填channel_id
- `/api/channels/delete` 刪除頻道，須包含參數channel_id
- `/api/channel/<channel_id>/join` 獲得加入Port
- `/api/channel/<channel_id>/leave` 離開頻道
- `/api/channel/<channel_id>/lan_ip` 取得頻道區域網列表，須包含參數name、lan_ip、port

## 運作原理(User flow)
- 首先使用者進入網站建立一個頻道，接著在`client.exe`(`client.py`, 以下簡稱客戶端)中填入頻道編號(channel_id)
- 客戶端先向伺服器進行`join`的POST請求，獲得伺服器的socket Port，接著透過socket向伺服器發送加入請求，此時伺服器可獲得客戶端用來進行P2P連線的最外層IP和Port並記錄至頻道成員列表中
- 客戶端會不斷更新成員列表，直到發現有新的成員加入時，會獲得其IP及Port，接著向其不斷送出UDP連線封包，與此同時新的成員也會開始向已經在頻道內的成員發送UDP連線封包，當兩個使用者端都接收到封包時，即表示連線成功，會送出10個確認封包並開始傳輸語音資料
- 若新的成員與已存在成員的IP相同，即代表兩使用者可能在相同區域網中(相同NAT)，兩客戶端會進行`lan_ip`的POST請求，交換區域網IP，交換完成後會嘗試透過取得的區域網IP和本機Port進行P2P連線
- 在收到exit命令或是偵測到`Ctrl+C`時，會停止所有的工作並向伺服器發送`leave`的POST請求，結束程式
- 很明顯目前沒有任何加密和身分認證的保護措施，所以拜託看到這裡的資安大佬們別把我當靶機> <