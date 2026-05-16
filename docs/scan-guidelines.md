# Shoe Scan Guidelines

## Goal

Capture enough visual coverage for the backend reconstruction pipeline to create or mock a one-mesh shoe model for visual customization.

## Recommended Capture

- Keep the full shoe inside the overlay guide.
- Record for 30 to 60 seconds.
- Move around the shoe slowly.
- Keep lighting bright and even.
- Use a plain background.
- Include a scale reference such as A4 paper, ruler, or printed marker.

## Metadata to Collect

```json
{
  "shoe": {
    "sizeSystem": "EU",
    "size": "42",
    "side": "left",
    "type": "sneaker",
    "material": "canvas",
    "condition": "used"
  },
  "measurements": {
    "lengthCm": 27.0,
    "widthCm": 9.5
  },
  "scanSetup": {
    "calibrationReference": "A4 paper",
    "lighting": "bright",
    "background": "plain"
  },
  "customizationGoal": [
    "change_color",
    "add_sticker",
    "add_text"
  ]
}
```

## MVP Limits

The mobile app should only capture and upload video plus metadata. Reconstruction happens on the backend.
