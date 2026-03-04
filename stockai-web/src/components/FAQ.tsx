import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Container,
  Stack,
  Typography,
} from '@mui/material'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import { GradientOverline } from '../themes/styles'

const faqs = [
  {
    question: 'Is this real trading?',
    answer: 'No. StockTrAIder is a learning platform with virtual trades only.',
  },
  {
    question: 'Where does the data come from?',
    answer: 'We use historical market data dating back to the 1970s.',
  },
  {
    question: 'Who is this for?',
    answer: 'Students, new traders, and anyone who wants a clear view of market history.',
  },
]

export default function FAQ() {
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 6, md: 10 } }}>
      <Stack spacing={1} sx={{ mb: 6 }}>
        <GradientOverline>Got questions?</GradientOverline>
        <Typography variant="h3" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
          Frequently asked
        </Typography>
      </Stack>

      <Box sx={{ maxWidth: 680 }}>
        {faqs.map((item, i) => (
          <Accordion
            key={item.question}
            disableGutters
            elevation={0}
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: '10px !important',
              mb: i < faqs.length - 1 ? 1.5 : 0,
              '&::before': { display: 'none' },
              '&.Mui-expanded': {
                borderColor: 'primary.main',
              },
              transition: 'border-color 0.2s',
            }}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreRoundedIcon sx={{ color: 'text.secondary' }} />}
              sx={{ px: 3, py: 0.5 }}
            >
              <Typography sx={{ fontWeight: 600 }}>{item.question}</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 3, pb: 2.5, pt: 0 }}>
              <Typography color="text.secondary" sx={{ lineHeight: 1.7 }}>
                {item.answer}
              </Typography>
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>
    </Container>
  )
}
