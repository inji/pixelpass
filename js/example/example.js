const open = require('open');
const express = require('express')
const path = require('path');
const {generateQRCode, generateQRData} = require('../src')
const QRCode = require("qrcode");
const {toQrPayload} = require("./qrPayload");
const {
    DEFAULT_QR_QUALITY,
    DEFAULT_QR_BORDER,
    DEFAULT_QR_SCALE,
    COLOR_BLACK,
    COLOR_WHITE, DEFAULT_ECC_LEVEL
} = require("../src/shared/Constants");

const app = express()
const port = 3000

app.use(express.text())
app.get('/', (req, res) => {
    const options = {
        root: path.join(__dirname)
    };
    res.sendFile("index.html", options)
})

app.get('/styles.css', (req, res) => {
    const options = {
        root: path.join(__dirname)
    };
    res.sendFile("stylesheet.css", options)
})

app.post('/qr', (req, res) => {
    let json = req.body;
    console.log("RECEIVED:", json);

    // Always encode input as JSON so decode() returns valid JSON: objects as-is,
    // strings (for example SD-JWT or JWT) as JSON strings. See INJIVER-1386.
    const qrPayload = toQrPayload(json);

    const opts = {
        errorCorrectionLevel: DEFAULT_ECC_LEVEL,
        quality: DEFAULT_QR_QUALITY,
        margin: DEFAULT_QR_BORDER,
        scale: DEFAULT_QR_SCALE,
        color: {
            dark: COLOR_BLACK,
            light: COLOR_WHITE
        }
    };

    try {
        const qrData = generateQRData(qrPayload);
        const version = QRCode.create(qrData, { errorCorrectionLevel: DEFAULT_ECC_LEVEL }).version;

        QRCode.toDataURL(qrData, opts).then(qr => res.send([version, qr]));
    } catch (err) {
        console.error("QR generation failed:", err);
        res.status(500).send("Error generating QR");
    }
});


app.listen(port, () => {
    console.log(`Example app listening on port ${port}`)
    open('http://localhost:3000');
})
