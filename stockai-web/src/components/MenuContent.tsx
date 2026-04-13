import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import HomeRoundedIcon from '@mui/icons-material/HomeRounded';
import AnalyticsRoundedIcon from '@mui/icons-material/AnalyticsRounded';
import AssignmentRoundedIcon from '@mui/icons-material/AssignmentRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import InfoRoundedIcon from '@mui/icons-material/InfoRounded';
import HelpRoundedIcon from '@mui/icons-material/HelpRounded';
import AttachMoneyIcon from "@mui/icons-material/AttachMoney";
import { useNavigate } from "react-router-dom";



export default function MenuContent() {
    const navigate = useNavigate();

    const mainListItems = [
        { text: 'Home', icon: <HomeRoundedIcon />, onClick: () => {navigate('/')} },
        { text: 'Analytics', icon: <AnalyticsRoundedIcon />, onClick: () => {} },
        { text: 'Earnings', icon: <AttachMoneyIcon />, onClick: () => {} },
        { text: 'Portfolio', icon: <AssignmentRoundedIcon />, onClick: () => {} },
    ];

    const secondaryListItems = [
        { text: 'Settings', icon: <SettingsRoundedIcon />, onClick: () => {} },
        { text: 'About', icon: <InfoRoundedIcon />, onClick: () => { navigate('/about') } },
        { text: 'Feedback', icon: <HelpRoundedIcon />, onClick: () => {} },
    ];

  return (
    <Stack sx={{ flexGrow: 1, p: 1, justifyContent: 'space-between' }}>
      <List dense>
        {mainListItems.map((item, index) => (
          <ListItem onClick={item.onClick} key={index} disablePadding sx={{ display: 'block' }}>
            <ListItemButton selected={index === 0}>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <List dense>
        {secondaryListItems.map((item, index) => (
          <ListItem onClick={item.onClick} key={index} disablePadding sx={{ display: 'block' }}>
            <ListItemButton>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Stack>
  );
}
