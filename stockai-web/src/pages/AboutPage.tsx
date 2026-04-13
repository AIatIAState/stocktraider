import {
  Avatar,
  Box,
  Card,
  CardContent,
  Chip,
  Container,
  Divider,
  Stack,
  Typography,
} from '@mui/material'
import IconButton from '@mui/material/IconButton'
import LinkedInIcon from '@mui/icons-material/LinkedIn'
import GitHubIcon from '@mui/icons-material/GitHub'
import masonPic from '../assets/masonPic.JPG'
import ethanPic from '../assets/ethanPic.JPG'
import AppAppBar from '../components/AppAppBar'
import Footer from '../components/Footer'
import AppTheme from '../themes/AppTheme'
import { GradientOverline, GradientText } from '../themes/styles'

interface Author {
  name: string
  role: string
  bio: string
  imageUrl?: string
  skills: string[]
  linkedInUrl?: string
  githubUrl?: string
}

const AUTHORS: Author[] = [
  {
    name: 'Mason Inman',
    role: 'Full-Stack Developer',
    bio: 'PHD student in Computer Engineering and MS in AI student at Iowa State University. Background in software engineering, machine learning, and artificial intelligence research.',
    skills: ['AI', 'ML','Python', 'FastAPI', 'SQLite', 'React', 'CI/CD', 'Docker', 'Nginx'],
    imageUrl: masonPic,
    linkedInUrl: 'https://www.linkedin.com/in/mason-inman/',
    githubUrl: 'https://github.com/MasonInman29'
  },
  {
    name: 'Ethan Gruening',
    role: 'Full-Stack Developer',
    bio: 'MS in AI student at Iowa State University. Background in software developement, machine learning, and a passion for creative applications of AI.',
    skills: ['ML', 'Python', 'NumPy', 'TypeScript', 'React', 'FastAPI', 'Docker', 'SQLite'],
    imageUrl: ethanPic,
    linkedInUrl: 'https://www.linkedin.com/in/ethan-gruening/',
    githubUrl: 'https://github.com/Ethan5026'
  },
]

function AuthorCard({ author }: { author: Author }) {
  const initials = author.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()

  return (
    <Card
      variant="outlined"
      sx={{
        flex: 1,
        minWidth: 280,
        borderRadius: 3,
        transition: 'box-shadow 0.2s',
        '&:hover': { boxShadow: 6 },
      }}
    >
      <CardContent sx={{ p: 4 }}>
        <Stack spacing={2.5} alignItems="center" textAlign="center">
          {author.imageUrl ? (
            <Avatar
              src={author.imageUrl}
              alt={author.name}
              sx={{ width: 120, height: 120, fontSize: '2.5rem' }}
            />
          ) : (
            <Avatar
              sx={{
                width: 120,
                height: 120,
                fontSize: '2.5rem',
                fontWeight: 700,
                background: 'linear-gradient(135deg, #1B224B 0%, #3a4a8a 100%)',
                color: '#00D3AB',
              }}
            >
              {initials}
            </Avatar>
          )}

          <Box>
            <Typography variant="h6" fontWeight={700}>
              {author.name}
            </Typography>
            <Typography
              variant="body2"
              sx={{
                background: 'linear-gradient(90deg, #7986CB 0%, #00D3AB 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                fontWeight: 600,
                mt: 0.25,
              }}
            >
              {author.role}
            </Typography>
          </Box>

          <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
            {author.bio}
          </Typography>

          <Stack direction="row" flexWrap="wrap" gap={1} justifyContent="center">
            {author.skills.map((skill) => (
              <Chip key={skill} label={skill} size="small" variant="outlined" />
            ))}
          </Stack>

          {(author.linkedInUrl || author.githubUrl) && (
            <Stack direction="row" spacing={0.5} justifyContent="center">
              {author.linkedInUrl && (
                <IconButton
                  component="a"
                  href={author.linkedInUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="small"
                  sx={{ color: '#0A66C2' }}
                >
                  <LinkedInIcon />
                </IconButton>
              )}
              {author.githubUrl && (
                <IconButton
                  component="a"
                  href={author.githubUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  size="small"
                >
                  <GitHubIcon />
                </IconButton>
              )}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  )
}

export default function AboutPage(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props}>
      <AppAppBar />

      <Container maxWidth="lg" sx={{ py: { xs: 6, md: 10 } }}>
        <Stack spacing={10}>

          {/* Hero */}
          <Box textAlign="center">
            <GradientOverline>About the Project</GradientOverline>
            <Typography variant="h3" fontWeight={800} sx={{ mt: 1, mb: 2 }}>
              StockTr<GradientText>AI</GradientText>der
            </Typography>
            <Typography
              variant="h6"
              color="text.secondary"
              sx={{ maxWidth: 640, mx: 'auto', lineHeight: 1.7, fontWeight: 400 }}
            >
              An AI-powered stock analysis platform built as a creative component for COMS 5990 at
              Iowa State University. It aims to bring real-world ML analysis to the common user by feeding powerful ML context that generates LLM insights.
            </Typography>
          </Box>

          {/* Team */}
          <Box>
            <Stack spacing={1} alignItems="center" textAlign="center" sx={{ mb: 5 }}>
              <GradientOverline>The Team</GradientOverline>
              <Typography variant="h4" fontWeight={700}>
                Meet the Authors
              </Typography>
            </Stack>

            <Stack
              direction={{ xs: 'column', md: 'row' }}
              spacing={3}
              justifyContent="center"
            >
              {AUTHORS.map((author) => (
                <AuthorCard key={author.name} author={author} />
              ))}
            </Stack>
          </Box>

          <Divider />

          {/* Acknowledgements */}
          <Box>
            <Stack spacing={1} alignItems="center" textAlign="center" sx={{ mb: 5 }}>
              <GradientOverline>Acknowledgements</GradientOverline>
              <Typography variant="h4" fontWeight={700}>
                Thank you
              </Typography>
            </Stack>

            <Card
              variant="outlined"
              sx={{
                borderRadius: 3,
                maxWidth: 680,
                mx: 'auto',
              }}
            >
              <CardContent sx={{ p: 4 }}>
                <Stack spacing={2.5} alignItems="center" textAlign="center">
                  <Avatar
                    sx={{
                      width: 96,
                      height: 96,
                      fontSize: '2rem',
                      fontWeight: 700,
                      background: 'linear-gradient(135deg, #7986CB 0%, #00D3AB 100%)',
                      color: '#fff',
                    }}
                  >
                    HP
                  </Avatar>

                  <Box>
                    <Typography variant="h6" fontWeight={700}>
                      Dr. Hung Phan
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        background: 'linear-gradient(90deg, #7986CB 0%, #00D3AB 100%)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        backgroundClip: 'text',
                        fontWeight: 600,
                        mt: 0.25,
                      }}
                    >
                      Project Client
                    </Typography>
                  </Box>

                  <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                    Thank you Dr. Hung Phan for his guidance, support, and
                    vision throughout this project. As our project client, Dr. Phan
                    provided direction and ensured academic rigor in our approach to AI-driven market analysis.
                  </Typography>
                </Stack>
              </CardContent>
            </Card>
          </Box>

          <Divider />

          {/* Project Info */}
          <Box>
            <Stack spacing={1} alignItems="center" textAlign="center" sx={{ mb: 5 }}>
              <GradientOverline>Project Details</GradientOverline>
              <Typography variant="h4" fontWeight={700}>
                Technical Overview
              </Typography>
            </Stack>

            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={3}
              justifyContent="center"
              flexWrap="wrap"
            >
              {[
                {
                  label: 'Course',
                  value: 'COMS 5990 - Creative Component',
                  sub: 'Iowa State University Department of Computer Science',
                },
                {
                  label: 'Stack',
                  value: 'React + FastAPI',
                  sub: 'TypeScript, Python, MUI, SQLite, Docker',
                },
                {
                  label: 'AI / ML',
                  value: 'OpenAI GPT + XGBoost',
                  sub: 'Darts, LLM prompting, feature engineering, and more',
                },
              ].map((item) => (
                <Card
                  key={item.label}
                  variant="outlined"
                  sx={{ borderRadius: 3, flex: '1 1 200px', maxWidth: 260 }}
                >
                  <CardContent sx={{ textAlign: 'center', p: 3 }}>
                    <Typography
                      variant="overline"
                      sx={{
                        background: 'linear-gradient(90deg, #7986CB 0%, #00D3AB 100%)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        backgroundClip: 'text',
                        fontWeight: 700,
                        letterSpacing: '0.1em',
                      }}
                    >
                      {item.label}
                    </Typography>
                    <Typography variant="subtitle1" fontWeight={700} sx={{ mt: 0.5 }}>
                      {item.value}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {item.sub}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Stack>
          </Box>

        </Stack>
      </Container>

      <Footer />
    </AppTheme>
  )
}
