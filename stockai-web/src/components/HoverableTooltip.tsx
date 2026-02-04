import { Tooltip, IconButton} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import type {ReactNode} from "react";

interface HoverableTooltipProps {
    children: ReactNode,
}
function HoverableTooltip(props: HoverableTooltipProps) {
    return (
        <Tooltip
            title={
                props.children
            }
            arrow
            enterDelay={200}
            leaveDelay={200}
            componentsProps={{
                tooltip: {
                    sx: {
                        bgcolor: 'grey.900',
                        '& .MuiTooltip-arrow': {
                            color: 'grey.900',
                        },
                        maxWidth: 300,
                    },
                },
            }}
            // These props make it stay open when hovering the tooltip itself
            PopperProps={{
                disablePortal: true,
                modifiers: [
                    {
                        name: 'offset',
                        options: {
                            offset: [0, -8],
                        },
                    },
                ],
            }}
            onMouseEnter={(e) => e.stopPropagation()}
        >
            <IconButton size="small">
                <InfoIcon fontSize="small" />
            </IconButton>
        </Tooltip>
    );
}

export default HoverableTooltip;