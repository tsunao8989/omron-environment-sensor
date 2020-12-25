# オムロン環境センサー（2JCIE-BL01）のデータを取得
Raspberry-pi でオムロン環境センサー（2JCIE-BL01）のデータを取得した際のスクリプト一式。
以下 Qiita の記事を参考に、取得したデータは Google スプレッドシートにアップロードしデータポータルで可視化する。

[Omron環境センサの値をRaspberryPiで定期ロギングする](https://qiita.com/c60evaporator/items/ed2ffde4c87001111c12)

記事の内容がわかりやすくとても参考になりました。

## 環境
- Raspberry-pi Pi 4 Computer Model B 4GB RAM
- Python 3.7.3


## セットアップ
パッケージ `libglib2.0-dev` のインストール

```bash
$ sudo apt install libglib2.0-dev
```

`bluepy` のインストールし `bluepy-helper` に sudo を許可。
``` bash
$ pip install bluepy
$ cd `pip3 show bluepy | grep "^Location:" | sed -e 's/^Location://' -e 's/ //g'`/bluepy
$ sudo setcap 'cap_net_raw,cap_net_admin+eip' bluepy-helper
```

