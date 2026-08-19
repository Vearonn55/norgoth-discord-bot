import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "NorBot Community Command Center";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 72,
          background: "linear-gradient(180deg, #0d121a 0%, #0b0e14 70%)",
          color: "#f1f4fa",
        }}
      >
        <div style={{ fontSize: 28, letterSpacing: "0.18em", color: "#6ea8fe" }}>
          NORBOT
        </div>
        <div style={{ fontSize: 56, fontWeight: 700, marginTop: 16, lineHeight: 1.15 }}>
          Community Command Center
        </div>
        <div style={{ fontSize: 24, marginTop: 24, color: "rgba(241,244,250,0.72)" }}>
          One Discord bot. One dashboard.
        </div>
      </div>
    ),
    size,
  );
}
