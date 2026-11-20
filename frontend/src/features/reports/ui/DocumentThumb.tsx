import { Box, Stack, Text } from "@mantine/core"

const line = (width: string, strong = false) => (
  <Box
    h={strong ? 4 : 3}
    w={width}
    bg={strong ? "#4a4f57" : "#d5d8dd"}
    style={{ borderRadius: 2 }}
  />
)

export function DocumentThumb({ qr, title, caption }: { qr: string; title: string; caption: string }) {
  return (
    <Box
      w={150}
      h={212}
      p={12}
      bg='white'
      aria-label={`Мініатюра звіту: ${title}`}
      role='img'
      className='app-no-select'
      style={{
        flexShrink: 0,
        borderRadius: 6,
        boxShadow: "0 1px 2px rgba(0,0,0,.25), 0 6px 18px rgba(0,0,0,.25)",
        position: "relative",
      }}
    >
      <Stack
        gap={5}
        align='center'
      >
        <Text
          fz={7}
          fw={700}
          c='#1f2328'
          ta='center'
          lh={1.2}
          lineClamp={2}
        >
          {title}
        </Text>
        <Text
          fz={6}
          c='#6b7280'
          ta='center'
          lh={1}
        >
          {caption}
        </Text>
      </Stack>
      <Stack
        gap={5}
        mt={10}
      >
        {line("100%", true)}
        {line("92%")}
        {line("96%")}
        {line("70%")}
        {line("100%", true)}
        {line("88%")}
        {line("94%")}
        {line("40%")}
      </Stack>
      <img
        src={qr}
        alt='QR-код перевірки справжності'
        width={54}
        height={54}
        style={{ position: "absolute", right: 10, bottom: 10, imageRendering: "pixelated" }}
      />
    </Box>
  )
}
