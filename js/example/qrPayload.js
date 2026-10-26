const toQrPayload = (rawInput) => {
    const input = typeof rawInput === "string" ? rawInput.trim() : "";

    // Preserve the example's previous behavior for an empty request body.
    if (!input) {
        return "{}";
    }

    try {
        const parsed = JSON.parse(input);
        return JSON.stringify(typeof parsed === "string" ? parsed.trim() : parsed);
    } catch (error) {
        return JSON.stringify(input);
    }
};

module.exports = {toQrPayload};
