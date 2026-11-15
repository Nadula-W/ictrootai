import type {Metadata} from 'next';
import './globals.css';
import './generation-setup.css';
export const metadata:Metadata={title:'ICTRoot AI · Learn with understanding',description:'Sri Lankan A/L ICT learning, practice and assessment'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
