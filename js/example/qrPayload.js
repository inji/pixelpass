const toQrPayload = (rawInput) => {
    const input = typeof rawInput === "string" ? rawInput.trim() : "";

    // Preserve the example's previous behavior for an empty request body.
    if (!input) {
        return "{}";
    }

    try {
        return JSON.stringify(JSON.parse(input));
    } catch (error) {
        return JSON.stringify(input);
    }
};

module.exports = {toQrPayload};
